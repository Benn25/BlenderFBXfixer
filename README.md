# Fusion 360 FBX Tools for Blender

A Blender addon that fixes the mess Fusion 360 creates when you export an assembly as FBX and import it into Blender.

Available on [Gumroad](https://blenderbenn.gumroad.com/l/kejkkd).

---

## The problem

When you export a Fusion 360 assembly as FBX and import it into Blender, you get two big issues:

1. **Wrong transforms** — scales and rotations are stored on objects but not applied. This breaks modifiers, physics, armatures, and basically anything you want to do with the model.
2. **Junk hierarchy** — Fusion 360 wraps every part in a chain of empty objects (invisible containers). Most of these are redundant — an empty that contains an empty that contains an empty, with no real geometry in sight. The outliner becomes a nightmare.

This addon fixes both, in seconds, on assemblies of any complexity.

---

## Features

### Fix Transforms
Select the root empty of your imported model and hit the button. The addon:
- Applies scale and/or rotation to the entire object hierarchy
- Detects instanced parts (e.g. repeated screws or bolts), temporarily makes them unique to apply transforms, then re-links them as shared instances — so you don't lose instancing
- Auto-sizes the root empty as a cube that wraps your model's bounding box, so it's always visible and proportional
- Optionally re-centers the root empty to the model's geometric center

### Clean Useless Empty Cascades
Removes redundant empty chains — any empty that only contains one other empty (with no geometry) gets collapsed out of the hierarchy. Keeps the meaningful structure, removes the noise.

### Replace Last Empty
At the tips of the hierarchy tree, if an empty only wraps a single mesh object, it removes the empty and promotes the mesh up in its place. Two options:
- **Replace + Rename** — the mesh takes the empty's name (useful when the empty has the part name you want to keep)
- **Replace (Keep Name)** — the mesh keeps its own original name

### Delete Empty & Reparent Children
A manual utility — delete any selected empty(s) and automatically move their children up to the grandparent, so nothing gets orphaned.

---

## Installation

1. Download the `.py` file
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the downloaded file and enable the addon

The panel appears in **View3D → Sidebar (N panel) → Edit tab**.

---

## Requirements

- Blender 2.80 or newer

---

## Important note

The **Fix Transforms** operation can crash Blender if you undo it. Always **save your file before running it**, and click somewhere else in the viewport immediately after it finishes (this dismisses the operator and reduces crash risk).

---

## Compatibility

Tested with Fusion 360 FBX exports. Works on assemblies of any size — the more complex the assembly, the bigger the time saving.
