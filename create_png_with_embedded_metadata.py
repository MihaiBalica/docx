from PIL import Image, PngImagePlugin
import os

os.makedirs("Images", exist_ok=True)
img = Image.new("RGB", (200, 200), color="blue")

meta = PngImagePlugin.PngInfo()
meta.add_text("HiddenMessage", "This is simulated metadata payload")

img.save("Images/stego_test.png", pnginfo=meta)
print("PNG with embedded metadata created.")