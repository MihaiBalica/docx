import os

path = os.getcwd()
os.makedirs(path, exist_ok=True)

eicar_string = (
    "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)
with open(os.path.join(path, "this_file_got-covid19.txt"), "w") as f:
    f.write(eicar_string)

print("EICAR test file created at", os.path.abspath(path))
print("To archive: powershell -command \"Compress-Archive -Path 'C:\\path\\to\\folder' -DestinationPath 'C:\\path\\to\\archive.zip' -Force\"")