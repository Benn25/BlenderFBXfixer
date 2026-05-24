# My Working Preferences

## Who I am
- No command line experience — I do not use terminal commands myself
- I work across devices (PC, phone, browser)
- I have experience with Arduino and Blender addons, but in a basic/dirty way
- I am not a professional developer

## How I want Claude to work

### Git & GitHub
- Claude handles ALL git operations (commit, push, branch, etc.)
- I only do one thing on GitHub: click the banner → Create pull request → Merge
- Every logical change must be its own separate commit so I can accept or reject changes individually
- Never bundle unrelated changes into one commit

### File structure — mandatory on every session start
- At the start of every session, review the project file structure
- Identify what type of project it is (Blender addon, Arduino/PlatformIO, etc.)
- Suggest what a standard/clean file structure should look like for that project type
- **Always ask for explicit approval before moving, renaming, or creating any files** — sometimes I may not want restructuring even if it would be cleaner

#### Blender addon rules
- Single file, under 500 lines → keep as one `.py` file, no folder, keep the addon name as the filename
- Single file, over 500 lines → propose converting to a folder with `__init__.py`, `operators.py`, `ui.py`, `utils.py` — wait for approval first
- Already multi-file → propose wrapping in a folder if not already done — wait for approval

#### Arduino / PlatformIO rules
- Project should follow PlatformIO structure: `src/main.cpp`, `include/`, `lib/`, `platformio.ini`
- Suggest splitting large `.ino` or `.cpp` files into logical modules when appropriate — wait for approval before doing it

### Code explanations — verbosity rules
- **Python**: Be verbose. Explain what non-obvious code does, how it works, and why. I am not strong in Python and I want to understand how things work.
- **C++**: Explain and comment only smart or non-obvious things. I am more familiar with C++/Arduino so don't over-explain basic concepts.
- In both languages: never write comments that just repeat what the variable name already says.

### General
- Keep explanations in plain language — assume I am not a developer by trade
- Never ask me to run commands in a terminal
- If something needs doing, Claude does it
