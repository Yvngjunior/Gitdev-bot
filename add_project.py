import json
import os

PROJECTS_FILE = ".devbot_projects.json"

# Load existing projects
if os.path.exists(PROJECTS_FILE):
    with open(PROJECTS_FILE) as f:
        data = json.load(f)
else:
    data = {"projects": {}, "default": None}

# Ask user for project name and path
name = input("Enter the new project name: ").strip()
path = input("Enter the full path to the project folder: ").strip()

# Add to projects
data["projects"][name] = path

# Optionally update default project
set_default = input("Set this as default project? (y/n): ").strip().lower()
if set_default == "y":
    data["default"] = name

# Save JSON
with open(PROJECTS_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Project '{name}' added successfully!")
