import os
import zipfile
import argparse

parser = argparse.ArgumentParser(description="Create nested zips with recursion.")
parser.add_argument("--destination", help="Destination directory for nested zips")
args = parser.parse_args()

base = args.destination
os.makedirs(base, exist_ok=True)

# Create nested zips
level_path = base
for i in range(1, 7):
    zip_name = os.path.join(level_path, f"level_{i}.zip")
    inner_folder = os.path.join(level_path, f"folder_{i}")
    os.makedirs(inner_folder, exist_ok=True)
    with open(os.path.join(inner_folder, f"file_{i}.txt"), "w") as f:
        f.write(f"This is level {i}")
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(inner_folder, f"file_{i}.txt"), f"file_{i}.txt")
    level_path = inner_folder
print("Nested zips created under", base)