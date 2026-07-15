"""Render the CamBridge app icon (clean camera lens + live dot on brand blue)."""
from PIL import Image, ImageDraw

TOP = (43, 147, 240)
BOT = (0, 97, 193)
WHITE = (255, 255, 255, 255)
GREEN = (46, 200, 110, 255)
DEEP = (0, 79, 158, 255)


def render(size, ss=8):
    W = size * ss
    grad = Image.new("RGB", (1, W))
    for y in range(W):
        t = y / (W - 1)
        grad.putpixel((0, y), tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)))
    grad = grad.resize((W, W))
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=int(0.225 * W), fill=255)
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    cx = cy = W // 2
    Rout = int(0.255 * W)
    ring = max(2, int(0.055 * W))
    d.ellipse([cx - Rout, cy - Rout, cx + Rout, cy + Rout], outline=WHITE, width=ring)
    Rin = int(0.15 * W)
    d.ellipse([cx - Rin, cy - Rin, cx + Rin, cy + Rin], fill=WHITE)
    ap = int(0.058 * W)
    d.ellipse([cx - ap, cy - ap, cx + ap, cy + ap], fill=DEEP)
    hh = int(0.055 * W)
    ox = cx - Rin + int(0.022 * W)
    oy = cy - Rin + int(0.022 * W)
    d.ellipse([ox, oy, ox + hh, oy + hh], fill=WHITE)

    lx = int(cx + Rout * 0.70)
    ly = int(cy - Rout * 0.70)
    ld = int(0.062 * W)
    sep = max(1, ring // 2)
    d.ellipse([lx - ld - sep, ly - ld - sep, lx + ld + sep, ly + ld + sep], fill=WHITE)
    d.ellipse([lx - ld, ly - ld, lx + ld, ly + ld], fill=GREEN)

    return img.resize((size, size), Image.LANCZOS)


render(1024).save("CamBridge.png")
sizes = [16, 24, 32, 48, 64, 128, 256]
render(256).save("CamBridge.ico", format="ICO", sizes=[(s, s) for s in sizes])
# quick legibility proof sheet at small sizes
for s in (16, 32, 48):
    render(s).resize((s * 4, s * 4), Image.NEAREST).save(f"proof_{s}.png")
print("wrote CamBridge.png (1024) and CamBridge.ico", sizes)
