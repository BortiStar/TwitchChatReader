from PIL import Image

img = Image.open("icon.png")
# .ico требует квадрат; приводим к 256x256 (максимум, который читает Windows)
img = img.convert("RGBA").resize((256, 256))
img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon.ico готов")