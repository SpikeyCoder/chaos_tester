"""Generate static/apple-touch-icon.png (180x180) from the brand mark.

Recreates static/favicon.svg as a raster PNG so iOS "Add to Home
Screen" / bookmark requests for /apple-touch-icon.png resolve instead
of 404ing. Rendered at 4x and downsampled for antialiased edges.

Run from the chaos_tester repo root:

    python3 gen_apple_touch_icon.py
"""
from PIL import Image, ImageDraw

SIZE = 180
SS = 4  # supersample factor
S = SIZE * SS

BG = (0, 0, 0)            # favicon rect fill #000
BLUE = (0, 191, 255)      # favicon arc stroke #00BFFF
WHITE = (255, 255, 255)

img = Image.new("RGB", (S, S), BG)
d = ImageDraw.Draw(img)

# favicon.svg uses a 0..100 viewBox; scale into the supersampled canvas.
sc = S / 100.0
cx = cy = 50 * sc

# Two concentric 270-degree arcs with the gap at the bottom-left,
# matching favicon.svg's outer (r=38, w=7) and inner (r=30, w=6) arcs.
# PIL angles: 0=3 o'clock, increasing clockwise. Drawing 180->90
# clockwise sweeps 270 degrees and leaves the 90..180 (bottom-left)
# sector open.
for r, w in ((38, 7), (30, 6)):
    rr, ww = r * sc, w * sc
    d.arc(
        [cx - rr, cy - rr, cx + rr, cy + rr],
        start=180, end=90, fill=BLUE, width=int(round(ww)),
    )

# White dot near the top-right (favicon: cx=72 cy=28 r=3.5).
dot_r = 3.5 * sc
d.ellipse(
    [72 * sc - dot_r, 28 * sc - dot_r, 72 * sc + dot_r, 28 * sc + dot_r],
    fill=WHITE,
)

# White checkmark (favicon polyline 34,52 -> 46,64 -> 68,38).
pts = [(34 * sc, 52 * sc), (46 * sc, 64 * sc), (68 * sc, 38 * sc)]
cw = int(round(7 * sc))
d.line(pts, fill=WHITE, width=cw)
# Round the caps/joins (PIL has no native round linecap).
for px, py in pts:
    d.ellipse([px - cw / 2, py - cw / 2, px + cw / 2, py + cw / 2], fill=WHITE)

img = img.resize((SIZE, SIZE), Image.LANCZOS)
img.save("static/apple-touch-icon.png")
print("apple-touch-icon saved to static/apple-touch-icon.png")
