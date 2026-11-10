"""
scripts/build_assets.py
=======================
Generates the project logo (original artwork) in every size/variant the project needs.

Concept: an *insight lens* (magnifier) containing a rising *route line* with stops -
ride data + analytics in one mark. Drawn with plain geometry so the PNG (PIL) and
SVG versions are identical in shape.

Outputs (assets/):
    logo_mark.png          512x512 badge, transparent corners
    logo_full.png          horizontal lock-up for LIGHT backgrounds (dark text)
    logo_full_light.png    horizontal lock-up for DARK backgrounds (white text)
    favicon.png            64x64
    logo.svg / logo_full.svg

Run:  python scripts/build_assets.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)

INK, LIME, PAPER, MUTED = "#0F1A17", "#C6E22A", "#F4F6F1", "#5E6B66"
SS = 4  # supersampling factor for smooth edges

# ---- geometry (512 x 512 design grid) -------------------------------------
RING_C, RING_R, RING_W = (232, 232), 150, 34
HANDLE = ((338, 338), (428, 428), 46)
ROUTE = [(150, 282), (205, 228), (250, 262), (318, 186)]
ROUTE_W = 20
FONT_DIR = Path("/usr/share/fonts/opentype/inter")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:                                   # font missing -> PIL default
        return ImageFont.load_default()


def draw_mark(size: int = 512, badge: bool = True) -> Image.Image:
    """Draw the badge at ``size`` px (supersampled internally)."""
    s = size * SS / 512.0
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sc = lambda v: v * s                                           # noqa: E731 - tiny helper

    if badge:
        d.rounded_rectangle([0, 0, 512 * s - 1, 512 * s - 1], radius=112 * s, fill=INK)

    cx, cy = RING_C
    outer, inner = RING_R + RING_W / 2, RING_R - RING_W / 2
    d.ellipse([sc(cx - outer), sc(cy - outer), sc(cx + outer), sc(cy + outer)], fill=LIME)
    d.ellipse([sc(cx - inner), sc(cy - inner), sc(cx + inner), sc(cy + inner)], fill=INK)

    (x1, y1), (x2, y2), w = HANDLE
    d.line([sc(x1), sc(y1), sc(x2), sc(y2)], fill=LIME, width=int(sc(w)))
    for x, y in ((x1, y1), (x2, y2)):                              # round caps
        d.ellipse([sc(x - w / 2), sc(y - w / 2), sc(x + w / 2), sc(y + w / 2)], fill=LIME)

    pts = [(sc(x), sc(y)) for x, y in ROUTE]
    d.line(pts, fill=PAPER, width=int(sc(ROUTE_W)), joint="curve")
    for x, y in ROUTE[:3]:                                         # stops
        r = 14
        d.ellipse([sc(x - r), sc(y - r), sc(x + r), sc(y + r)], fill=PAPER)
    ex, ey = ROUTE[-1]                                             # destination node
    d.ellipse([sc(ex - 24), sc(ey - 24), sc(ex + 24), sc(ey + 24)], fill=LIME)
    d.ellipse([sc(ex - 9), sc(ey - 9), sc(ex + 9), sc(ey + 9)], fill=INK)

    return img.resize((size, size), Image.LANCZOS)


def draw_lockup(dark_text: bool, height: int = 220) -> Image.Image:
    """Horizontal lock-up: mark + 'Ola' + 'Ride Insights'."""
    text_main = INK if dark_text else "#FFFFFF"
    text_sub = MUTED if dark_text else "#B9C4BE"
    mark = draw_mark(height)
    width = int(height * 4.1)
    img = Image.new("RGBA", (width * SS, height * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    img.paste(mark.resize((height * SS, height * SS), Image.LANCZOS), (0, 0))
    big = _font("InterDisplay-ExtraBold.otf", int(height * 0.50 * SS))
    small = _font("Inter-Medium.otf", int(height * 0.215 * SS))
    x0 = int(height * 1.18 * SS)
    d.text((x0, int(height * 0.12 * SS)), "Ola", font=big, fill=text_main)
    d.text((x0 + int(height * 0.03 * SS), int(height * 0.66 * SS)), "Ride Insights", font=small, fill=text_sub)
    bbox = img.getbbox()
    img = img.crop((0, 0, min(img.width, bbox[2] + 6 * SS), img.height))
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


# ---- SVG (hand-written, same geometry) ------------------------------------
def mark_svg_body() -> str:
    cx, cy = RING_C
    (x1, y1), (x2, y2), w = HANDLE
    route = " ".join(f"{x},{y}" for x, y in ROUTE)
    stops = "".join(f'<circle cx="{x}" cy="{y}" r="14" fill="{PAPER}"/>' for x, y in ROUTE[:3])
    ex, ey = ROUTE[-1]
    return (
        f'<rect width="512" height="512" rx="112" fill="{INK}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{RING_R}" fill="none" stroke="{LIME}" stroke-width="{RING_W}"/>'
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LIME}" stroke-width="{w}" stroke-linecap="round"/>'
        f'<polyline points="{route}" fill="none" stroke="{PAPER}" stroke-width="{ROUTE_W}" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{stops}<circle cx="{ex}" cy="{ey}" r="24" fill="{LIME}"/><circle cx="{ex}" cy="{ey}" r="9" fill="{INK}"/>'
    )


def write_svgs() -> None:
    body = mark_svg_body()
    (OUT / "logo.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Ola Ride Insights logo">{body}</svg>')
    (OUT / "logo_full.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 512" role="img" aria-label="Ola Ride Insights">'
        f'{body}<text x="580" y="290" font-family="Inter, Arial, sans-serif" font-weight="800" font-size="250" fill="{INK}">Ola</text>'
        f'<text x="590" y="400" font-family="Inter, Arial, sans-serif" font-weight="500" font-size="100" fill="{MUTED}">Ride Insights</text></svg>')


def main() -> None:
    draw_mark(512).save(OUT / "logo_mark.png")
    draw_mark(64).save(OUT / "favicon.png")
    draw_lockup(dark_text=True).save(OUT / "logo_full.png")
    draw_lockup(dark_text=False).save(OUT / "logo_full_light.png")
    write_svgs()
    print("Wrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
