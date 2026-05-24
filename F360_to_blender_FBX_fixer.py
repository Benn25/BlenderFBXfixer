bl_info = {
    "name": "Fusion 360 FBX Tools V3.6",
    "author": "Benn",
    "version": (3, 6, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Edit Tab",
    "description": "Fixes transforms and cleans up empties in Fusion 360 FBX imports.",
    "category": "Object",
}

import bpy
from collections import defaultdict
from mathutils import Vector

# --------- Utility Functions ---------

def collect_all_children(parent):
    result = []
    for child in parent.children:
        result.append(child)
        result.extend(collect_all_children(child))
    return result

def set_empty_display_size(obj, base_size, factor, level=0):
    for child in obj.children:
        if child.type == 'EMPTY':
            size = base_size * (factor ** level)
            child.empty_display_size = size
            set_empty_display_size(child, base_size, factor, level + 1)

def get_mesh_bounding_box_world(mesh_objs):
    coords = []
    for obj in mesh_objs:
        if obj.type == 'MESH':
            coords.extend([obj.matrix_world @ Vector(corner) for corner in obj.bound_box])
    if not coords:
        return None, None
    min_v = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
    max_v = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
    return min_v, max_v

def get_bbox_center_and_size(min_v, max_v):
    center = (min_v + max_v) * 0.5
    size = max_v - min_v
    return center, max(size.x, size.y, size.z)

def move_main_empty_without_affecting_children(main_empty, new_location):
    delta = new_location - main_empty.location
    for child in main_empty.children:
        child.location -= delta
    main_empty.location = new_location

def get_hierarchy_depth(obj):
    depth = 0
    p = obj.parent
    while p:
        depth += 1
        p = p.parent
    return depth

# --------- Empty Display Logic ---------

def set_empty_displays(main_empty, scene):
    main_empty.show_name = scene.f360fbx_show_empty_names
    for child in main_empty.children:
        if child.type == 'EMPTY':
            child.empty_display_type = scene.f360fbx_first_child_display
            child.show_name = scene.f360fbx_show_empty_names
            set_last_empties_display(child, scene)

def set_last_empties_display(empty, scene):
    empty_children = [c for c in empty.children if c.type == 'EMPTY']
    if not empty_children:
        empty.empty_display_type = scene.f360fbx_last_empty_display
    else:
        for c in empty_children:
            set_last_empties_display(c, scene)

# --------- Part 1: Transform Fixer ---------

class F360FBX_OT_fix_transform(bpy.types.Operator):
    bl_idname = "object.f360fbx_fix_transform"
    bl_label = "Fix Fusion 360 FBX Transforms"
    bl_description = "Apply selected transforms to all children of the selected object, preserving instancing"
    bl_options = {"REGISTER"}

    apply_rotation: bpy.props.BoolProperty(name="Rotation", default=False)
    apply_scale: bpy.props.BoolProperty(name="Scale", default=True)
    main_empty_size: bpy.props.FloatProperty(
        name="Main Empty Size", default=1.0, min=0.01, description="Display size for the main empty"
    )
    child_empty_size: bpy.props.FloatProperty(
        name="Child Empty Base Size", default=0.2, min=0.01, description="Display size for first-level child empties"
    )
    empty_size_factor: bpy.props.FloatProperty(
        name="Child Size Factor", default=0.5, min=0.01, max=2.0,
        description="Multiplier for empty size at each hierarchy level"
    )
    center_main_empty: bpy.props.BoolProperty(
        name="Center Main Empty to Geometry", default=False, description="Move the main empty to the center of the model's bounding box"
    )
    autosize_main_empty: bpy.props.BoolProperty(
        name="Auto-size Main Empty", default=True, description="Set main empty display size to fit model bounding box"
    )

    def execute(self, context):
        # Ensure we're in Object Mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        main_empty = context.active_object
        if not main_empty or main_empty.type != 'EMPTY':
            self.report({'ERROR'}, "Please select the main empty object.")
            return {'CANCELLED'}

        all_objs = [main_empty] + collect_all_children(main_empty)
        mesh_objs = [obj for obj in all_objs if obj.type == 'MESH']

        if not mesh_objs:
            self.report({'ERROR'}, "No mesh objects found in hierarchy.")
            return {'CANCELLED'}

        # 1. Record instancing: mesh name -> list of objects
        mesh_to_objs = defaultdict(list)
        for obj in mesh_objs:
            mesh_to_objs[obj.data.name].append(obj)
        instanced_meshes = {name: objs for name, objs in mesh_to_objs.items() if len(objs) > 1}

        # 2. Make all mesh data single-user
        bpy.ops.object.select_all(action='DESELECT')
        for obj in mesh_objs:
            obj.select_set(True)
        context.view_layer.objects.active = mesh_objs[0]
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)

        # 3. Apply transforms to the whole hierarchy
        bpy.ops.object.select_all(action='DESELECT')
        for obj in all_objs:
            obj.select_set(True)
        context.view_layer.objects.active = main_empty
        bpy.ops.object.transform_apply(
            location=False,
            rotation=self.apply_rotation,
            scale=self.apply_scale
        )

        # 4. Restore instancing for all possible objects (those with identical mesh data)
        for mesh_name, objs in instanced_meshes.items():
            shared_mesh = objs[0].data
            for obj in objs:
                obj.data = shared_mesh

        # 5. Main empty display: set shape to cube and (optionally) size/location
        main_empty.empty_display_type = 'CUBE'
        mesh_objs_for_bbox = [obj for obj in all_objs if obj.type == 'MESH']
        min_v, max_v = get_mesh_bounding_box_world(mesh_objs_for_bbox)
        if min_v is not None and max_v is not None:
            center, cube_size = get_bbox_center_and_size(min_v, max_v)
            if self.autosize_main_empty:
                main_empty.empty_display_size = cube_size / 2.0
            else:
                main_empty.empty_display_size = self.main_empty_size
            if self.center_main_empty:
                move_main_empty_without_affecting_children(main_empty, center)

        set_empty_display_size(main_empty, self.child_empty_size, self.empty_size_factor, level=0)
        set_empty_displays(main_empty, context.scene)

        self.report({'WARNING'}, "Undo may crash. Save first! Click away after running to avoid crash.")
        return {'FINISHED'}

# --------- Part 2: Empty Cleaners and Branch Operators ---------

def collect_branch_objects_depth(root, level=0, out=None):
    if out is None:
        out = []
    out.append((root.name, level))
    for child in root.children:
        collect_branch_objects_depth(child, level+1, out)
    return out

def is_useless_empty_by_name(obj_name, root_name):
    if obj_name == root_name:
        return False
    obj = bpy.data.objects.get(obj_name)
    root = bpy.data.objects.get(root_name)
    if not obj or not root:
        return False
    if obj.type != 'EMPTY':
        return False
    if obj.parent and obj.parent.name == root_name:
        return False
    children = list(obj.children)
    if len(children) != 1:
        return False
    child = children[0]
    if child.type != 'EMPTY':
        return False
    for c in children:
        if c.type == 'MESH':
            return False
    return True

def clean_useless_empties(root):
    root_name = root.name
    branch = collect_branch_objects_depth(root)
    branch.sort(key=lambda x: -x[1])
    to_delete = []
    for obj_name, _ in branch:
        if is_useless_empty_by_name(obj_name, root_name):
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.parent is not None:
                to_delete.append(obj)
    for obj in to_delete:
        if obj.name not in bpy.data.objects:
            continue
        child = obj.children[0]
        child.matrix_world = child.matrix_world
        child.parent = obj.parent
        child.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
        bpy.data.objects.remove(obj)

def is_last_empty_with_object_by_name(obj_name, root_name):
    if obj_name == root_name:
        return False
    obj = bpy.data.objects.get(obj_name)
    root = bpy.data.objects.get(root_name)
    if not obj or not root:
        return False
    if obj.type != 'EMPTY':
        return False
    children = list(obj.children)
    if len(children) != 1:
        return False
    child = children[0]
    if child.type == 'EMPTY':
        return False
    return True

def replace_last_empty_with_object(root):
    root_name = root.name
    branch = collect_branch_objects_depth(root)
    branch.sort(key=lambda x: -x[1])
    to_delete = []
    for obj_name, _ in branch:
        if is_last_empty_with_object_by_name(obj_name, root_name):
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.parent is not None:
                to_delete.append(obj)
    for obj in to_delete:
        if obj.name not in bpy.data.objects:
            continue
        child = obj.children[0]
        child.matrix_world = child.matrix_world
        child.parent = obj.parent
        child.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
        bpy.data.objects.remove(obj)

def replace_last_empty_with_object_and_rename(root):
    root_name = root.name
    branch = collect_branch_objects_depth(root)
    branch.sort(key=lambda x: -x[1])
    to_delete = []
    for obj_name, _ in branch:
        if is_last_empty_with_object_by_name(obj_name, root_name):
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.parent is not None:
                to_delete.append(obj)
    for obj in to_delete:
        if obj.name not in bpy.data.objects:
            continue
        child = obj.children[0]
        child.matrix_world = child.matrix_world
        child.parent = obj.parent
        child.matrix_parent_inverse = obj.matrix_parent_inverse.copy()
        try:
            child.name = obj.name
        except Exception:
            pass
        bpy.data.objects.remove(obj)

def delete_empty_and_reparent_children(empty):
    parent = empty.parent
    children = list(empty.children)
    for child in children:
        child.matrix_world = child.matrix_world
        child.parent = parent
        if parent is not None:
            child.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.data.objects.remove(empty)

# --------- Operators ---------

class F360FBX_OT_clean_empties(bpy.types.Operator):
    bl_idname = "object.f360fbx_clean_empties"
    bl_label = "Clean Useless Empty Cascades"
    bl_description = (
        "Remove useless cascades of parented empties (single empty within single empty, no objects). "
        "Works on all selected empties and their descendants. Main empty's first child is preserved."
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(obj for obj in context.selected_objects if obj.type == 'EMPTY')

    def execute(self, context):
        empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
        for root in empties:
            clean_useless_empties(root)
        self.report({'INFO'}, "Useless empty cascades cleaned in selected branches. Main empty's first child preserved.")
        return {'FINISHED'}

class F360FBX_OT_replace_last_empty(bpy.types.Operator):
    bl_idname = "object.f360fbx_replace_last_empty"
    bl_label = "Replace (Keep Name)"
    bl_description = (
        "If the last empty in a branch has only one child object, replaces the empty with the object. "
        "Keeps the object's original name. Processes only the selected empty and its descendants."
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'EMPTY'

    def execute(self, context):
        root = context.active_object
        replace_last_empty_with_object(root)
        self.report({'INFO'}, "Last empties replaced by their single child object in selected branch (kept object names).")
        return {'FINISHED'}

class F360FBX_OT_replace_last_empty_rename(bpy.types.Operator):
    bl_idname = "object.f360fbx_replace_last_empty_rename"
    bl_label = "Replace + Rename"
    bl_description = (
        "If the last empty in a branch has only one child object, replaces the empty with the object "
        "and renames the object after the empty. Processes only the selected empty and its descendants."
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'EMPTY'

    def execute(self, context):
        root = context.active_object
        replace_last_empty_with_object_and_rename(root)
        self.report({'INFO'}, "Last empties replaced by their single child object and renamed in selected branch.")
        return {'FINISHED'}

class F360FBX_OT_delete_empty_reparent(bpy.types.Operator):
    bl_idname = "object.f360fbx_delete_empty_reparent"
    bl_label = "Delete Selected Empties (Reparent Children)"
    bl_description = "Reparent all children of selected empties to their parent, then delete the empties."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(obj for obj in context.selected_objects if obj.type == 'EMPTY')

    def execute(self, context):
        empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
        empties.sort(key=lambda obj: get_hierarchy_depth(obj), reverse=True)
        for empty in empties:
            if empty.name in bpy.data.objects:
                delete_empty_and_reparent_children(empty)
        self.report({'INFO'}, "Selected empties deleted and children reparented.")
        return {'FINISHED'}

# --------- Unified Panel ---------

class F360FBX_PT_tools(bpy.types.Panel):
    bl_label = "Fusion 360 FBX Tools V3.6"
    bl_idname = "F360FBX_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Undo may crash. Save first!", icon="ERROR")
        box.label(text="Click away after running to avoid crash.")
        layout.separator()
        layout.label(text="Apply to Selected Hierarchy:")
        layout.prop(context.scene, "f360fbx_apply_rotation")
        if context.scene.f360fbx_apply_rotation:
            layout.label(text="Applying rotation will make all instances unique", icon='ERROR')
        layout.prop(context.scene, "f360fbx_apply_scale")
        layout.separator()
        layout.label(text="Main Empty Controls:")
        layout.prop(context.scene, "f360fbx_autosize_main_empty")
        row = layout.row()
        row.enabled = not context.scene.f360fbx_autosize_main_empty
        row.prop(context.scene, "f360fbx_main_empty_size")
        layout.prop(context.scene, "f360fbx_center_main_empty")
        layout.separator()
        layout.label(text="Child Empty Display Size Controls:")
        layout.prop(context.scene, "f360fbx_child_empty_size")
        layout.prop(context.scene, "f360fbx_empty_size_factor")
        layout.separator()
        layout.label(text="Empty Display Options:")
        # Compact dropdowns with 60/40 split
        row = layout.row(align=True)
        row.scale_x = 1.0
        row.label(text="First Child Display", icon='EMPTY_AXIS')
        row.prop(context.scene, "f360fbx_first_child_display", text="", expand=False)
        row = layout.row(align=True)
        row.scale_x = 1.0
        row.label(text="Last Empty Display", icon='EMPTY_ARROWS')
        row.prop(context.scene, "f360fbx_last_empty_display", text="", expand=False)
        layout.prop(context.scene, "f360fbx_show_empty_names")
        op = layout.operator("object.f360fbx_fix_transform", icon="MODIFIER")
        op.apply_rotation = context.scene.f360fbx_apply_rotation
        op.apply_scale = context.scene.f360fbx_apply_scale
        op.main_empty_size = context.scene.f360fbx_main_empty_size
        op.child_empty_size = context.scene.f360fbx_child_empty_size
        op.empty_size_factor = context.scene.f360fbx_empty_size_factor
        op.center_main_empty = context.scene.f360fbx_center_main_empty
        op.autosize_main_empty = context.scene.f360fbx_autosize_main_empty
        layout.separator()
        layout.operator("object.f360fbx_clean_empties", icon="X")
        layout.label(
            text="Replace last empty (with one object) by its child:",
            icon="INFO"
        )
        row = layout.row(align=True)
        row.operator("object.f360fbx_replace_last_empty_rename", text="Replace + Rename", icon="OUTLINER_OB_MESH")
        row.operator("object.f360fbx_replace_last_empty", text="Replace (Keep Name)", icon="OUTLINER_OB_MESH")
        layout.operator("object.f360fbx_delete_empty_reparent", icon="TRASH")

# --------- Registration ---------

def register():
    bpy.utils.register_class(F360FBX_OT_fix_transform)
    bpy.utils.register_class(F360FBX_OT_clean_empties)
    bpy.utils.register_class(F360FBX_OT_replace_last_empty)
    bpy.utils.register_class(F360FBX_OT_replace_last_empty_rename)
    bpy.utils.register_class(F360FBX_OT_delete_empty_reparent)
    bpy.utils.register_class(F360FBX_PT_tools)
    bpy.types.Scene.f360fbx_apply_rotation = bpy.props.BoolProperty(
        name="Apply Rotation", default=False)
    bpy.types.Scene.f360fbx_apply_scale = bpy.props.BoolProperty(
        name="Apply Scale", default=True)
    bpy.types.Scene.f360fbx_main_empty_size = bpy.props.FloatProperty(
        name="Main Empty Size", default=1.0, min=0.01)
    bpy.types.Scene.f360fbx_child_empty_size = bpy.props.FloatProperty(
        name="Child Empty Base Size", default=0.2, min=0.01)
    bpy.types.Scene.f360fbx_empty_size_factor = bpy.props.FloatProperty(
        name="Child Size Factor", default=0.5, min=0.01, max=2.0)
    bpy.types.Scene.f360fbx_center_main_empty = bpy.props.BoolProperty(
        name="Center Main Empty to Geometry", default=False)
    bpy.types.Scene.f360fbx_autosize_main_empty = bpy.props.BoolProperty(
        name="Auto-size Main Empty", default=True)
    bpy.types.Scene.f360fbx_first_child_display = bpy.props.EnumProperty(
        name="First Child Display",
        description="Display type for first child empties of the main empty",
        items=[
            ('PLAIN_AXES', "Plain Axes", ""),
            ('CUBE', "Cube", ""),
            ('SPHERE', "Sphere", ""),
            ('ARROWS', "Arrows", ""),
            ('CIRCLE', "Circle", ""),
            ('SINGLE_ARROW', "Single Arrow", ""),
            ('CONE', "Cone", ""),
        ],
        default='CUBE'
    )
    bpy.types.Scene.f360fbx_last_empty_display = bpy.props.EnumProperty(
        name="Last Empty Display",
        description="Display type for last empties in each branch",
        items=[
            ('PLAIN_AXES', "Plain Axes", ""),
            ('CUBE', "Cube", ""),
            ('SPHERE', "Sphere", ""),
            ('ARROWS', "Arrows", ""),
            ('CIRCLE', "Circle", ""),
            ('SINGLE_ARROW', "Single Arrow", ""),
            ('CONE', "Cone", ""),
        ],
        default='ARROWS'
    )
    bpy.types.Scene.f360fbx_show_empty_names = bpy.props.BoolProperty(
        name="Show Empty Names in Viewport",
        default=False,
        description="Show names of main and first child empties in the viewport"
    )

def unregister():
    del bpy.types.Scene.f360fbx_apply_rotation
    del bpy.types.Scene.f360fbx_apply_scale
    del bpy.types.Scene.f360fbx_main_empty_size
    del bpy.types.Scene.f360fbx_child_empty_size
    del bpy.types.Scene.f360fbx_empty_size_factor
    del bpy.types.Scene.f360fbx_center_main_empty
    del bpy.types.Scene.f360fbx_autosize_main_empty
    del bpy.types.Scene.f360fbx_first_child_display
    del bpy.types.Scene.f360fbx_last_empty_display
    del bpy.types.Scene.f360fbx_show_empty_names
    bpy.utils.unregister_class(F360FBX_PT_tools)
    bpy.utils.unregister_class(F360FBX_OT_fix_transform)
    bpy.utils.unregister_class(F360FBX_OT_clean_empties)
    bpy.utils.unregister_class(F360FBX_OT_replace_last_empty)
    bpy.utils.unregister_class(F360FBX_OT_replace_last_empty_rename)
    bpy.utils.unregister_class(F360FBX_OT_delete_empty_reparent)

if __name__ == "__main__":
    register()
