from PIL import Image, ImageDraw

def make_icon(size, path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded rect background with gradient approximation
    r = int(size * 0.2)
    d.rounded_rectangle([0, 0, size, size], radius=r, fill=(15, 15, 15, 255))
    # Two-tone gradient bars (left teal, right pink)
    d.rounded_rectangle([size*0.1, size*0.15, size*0.9, size*0.85], radius=int(size*0.05), fill=(37, 244, 238, 255))
    # Play triangle
    cx, cy, w = size/2, size/2, size*0.18
    d.polygon([(cx-w*0.8, cy-w), (cx-w*0.8, cy+w), (cx+w*1.1, cy)], fill=(254, 44, 85, 255))
    img.save(path)
    print(f"wrote {path} {size}x{size}")

make_icon(192, "static/icon-192.png")
make_icon(512, "static/icon-512.png")
make_icon(96, "static/icon-96.png")
