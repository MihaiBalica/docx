import os

path = os.getcwd()
os.makedirs(path, exist_ok=True)

vb = 'MsgBox "This is a test macro"'
js = 'alert("Hello from test JS")'

with open(os.path.join(path, "macro.vbs"), "w") as f:
    f.write(vb)

with open(os.path.join(path, "script.js"), "w") as f:
    f.write(js)

print("Script test files created at", path)