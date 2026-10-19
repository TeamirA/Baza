"""Simple flat illustrations for the sample catalog (seed_products --with-photos).

Drawn with Pillow so the demo store has real uploaded photos without bundling
or downloading image files. Each product gets a front view and a closer
"detail" view (used as the hover photo). Shapes are drawn on a 1000×1000 grid
at 2× resolution and scaled down for smooth edges.
"""

import io

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1600
SCALE = 2  # supersampling
GRID = 1000

# slug -> (background top, background bottom, main colour, accent colour)
PALETTES = {
    "classic-cotton-tee": ("#f3efe7", "#e2dccf", "#3f5f8a", "#2e4769"),
    "everyday-hoodie": ("#ece9f3", "#d6d1e4", "#6b5b95", "#4f4272"),
    "canvas-cap": ("#f2ede4", "#e0d6c4", "#b5835a", "#8c6240"),
    "ceramic-mug": ("#e9f1ee", "#d2e3dc", "#2f5d50", "#24493f"),
    "linen-throw-pillow": ("#f4efe9", "#e5dccf", "#c9b79c", "#a8957a"),
    "soy-candle": ("#f6efe6", "#eadcc8", "#e8dcc6", "#b88a55"),
    "leather-card-holder": ("#f1ece6", "#ded3c6", "#8a4b2a", "#6a3820"),
    "canvas-tote-bag": ("#eef0ea", "#d9ddd0", "#d9ccb0", "#9c8d6d"),
    "steel-water-bottle": ("#e8eef3", "#cfdbe5", "#4a7a9b", "#2f566f"),
}


def _hex(colour):
    colour = colour.lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def _shade(colour, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in colour)


class _Canvas:
    def __init__(self, top, bottom):
        px = SIZE * SCALE
        self.image = Image.new("RGB", (px, px), top)
        draw = ImageDraw.Draw(self.image)
        for y in range(px):
            t = y / px
            draw.line([(0, y), (px, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        self.draw = draw
        self.k = px / GRID

    def p(self, *xy):
        return [v * self.k for v in xy]

    def shadow(self, cx, y, w):
        layer = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(layer).ellipse(self.p(cx - w / 2, y - w * 0.06, cx + w / 2, y + w * 0.06), fill=70)
        layer = layer.filter(ImageFilter.GaussianBlur(12 * self.k))
        self.image.paste((0, 0, 0), mask=layer)


def _tee(c, main, accent, hood=False, long_sleeves=False):
    d = c.draw
    sleeve_end = 330 if long_sleeves else 400
    body = [(330, 300), (420, 260), (580, 260), (670, 300), (820, sleeve_end), (760, sleeve_end + 70),
            (680, 380), (680, 760), (320, 760), (320, 380), (240, sleeve_end + 70), (180, sleeve_end)]
    if long_sleeves:
        body = [(330, 300), (420, 260), (580, 260), (670, 300), (790, 560), (720, 590),
                (680, 420), (680, 780), (320, 780), (320, 420), (280, 590), (210, 560)]
    d.polygon([tuple(c.p(x, y)) for x, y in body], fill=main)
    if hood:
        d.ellipse(c.p(400, 190, 600, 330), fill=accent)
        d.ellipse(c.p(440, 230, 560, 320), fill=_shade(accent, 0.75))
        d.rounded_rectangle(c.p(400, 560, 600, 680), radius=30 * c.k, fill=accent)
    else:
        d.ellipse(c.p(440, 240, 560, 300), fill=_shade(main, 0.7))
    d.line(c.p(320, 740, 680, 740), fill=accent, width=int(10 * c.k))


def _cap(c, main, accent):
    d = c.draw
    d.pieslice(c.p(300, 330, 700, 730), 180, 360, fill=main)
    d.ellipse(c.p(250, 500, 760, 580), fill=accent)
    d.rectangle(c.p(300, 520, 700, 535), fill=main)
    for x in (400, 500, 600):
        d.line(c.p(500, 335, x, 530), fill=_shade(main, 0.85), width=int(5 * c.k))
    d.ellipse(c.p(488, 322, 512, 346), fill=accent)


def _mug(c, main, accent):
    d = c.draw
    d.ellipse(c.p(590, 400, 760, 600), outline=main, width=int(42 * c.k))
    d.rounded_rectangle(c.p(300, 330, 640, 720), radius=40 * c.k, fill=main)
    d.ellipse(c.p(300, 300, 640, 370), fill=accent)
    d.ellipse(c.p(325, 312, 615, 358), fill=_shade(accent, 0.6))
    d.rounded_rectangle(c.p(340, 380, 380, 680), radius=20 * c.k, fill=_shade(main, 1.25))


def _pillow(c, main, accent):
    d = c.draw
    d.rounded_rectangle(c.p(250, 290, 750, 720), radius=90 * c.k, fill=main)
    d.rounded_rectangle(c.p(285, 325, 715, 685), radius=70 * c.k, outline=accent, width=int(6 * c.k))
    for y in range(360, 680, 40):
        d.line(c.p(300, y, 700, y), fill=_shade(main, 0.95), width=int(3 * c.k))


def _candle(c, main, accent):
    d = c.draw
    d.rounded_rectangle(c.p(330, 400, 670, 740), radius=50 * c.k, fill=accent)
    d.ellipse(c.p(330, 370, 670, 440), fill=main)
    d.rounded_rectangle(c.p(330, 520, 670, 620), radius=6 * c.k, fill=_hex("#f6f1e8"))
    d.line(c.p(500, 405, 500, 360), fill=(60, 50, 40), width=int(8 * c.k))
    d.ellipse(c.p(478, 270, 522, 370), fill=(247, 177, 67))
    d.ellipse(c.p(490, 310, 510, 362), fill=(255, 236, 170))


def _card_holder(c, main, accent):
    d = c.draw
    d.rounded_rectangle(c.p(395, 300, 625, 470), radius=14 * c.k, fill=(232, 236, 240))
    d.rounded_rectangle(c.p(420, 300, 600, 330), radius=6 * c.k, fill=(66, 110, 170))
    d.rounded_rectangle(c.p(330, 380, 670, 680), radius=40 * c.k, fill=main)
    d.line(c.p(360, 430, 640, 430), fill=accent, width=int(10 * c.k))
    d.rounded_rectangle(c.p(345, 395, 655, 665), radius=32 * c.k, outline=_shade(main, 1.3), width=int(4 * c.k))


def _tote(c, main, accent):
    d = c.draw
    d.arc(c.p(380, 200, 500, 460), 180, 360, fill=accent, width=int(22 * c.k))
    d.arc(c.p(500, 200, 620, 460), 180, 360, fill=accent, width=int(22 * c.k))
    d.polygon([tuple(c.p(x, y)) for x, y in [(300, 330), (700, 330), (730, 760), (270, 760)]], fill=main)
    d.rounded_rectangle(c.p(420, 470, 580, 600), radius=10 * c.k, outline=accent, width=int(8 * c.k))


def _bottle(c, main, accent):
    d = c.draw
    d.rounded_rectangle(c.p(390, 330, 610, 770), radius=70 * c.k, fill=main)
    d.rectangle(c.p(440, 280, 560, 340), fill=_shade(main, 0.9))
    d.rounded_rectangle(c.p(425, 210, 575, 290), radius=18 * c.k, fill=accent)
    d.rounded_rectangle(c.p(420, 380, 455, 720), radius=16 * c.k, fill=_shade(main, 1.3))
    d.rectangle(c.p(390, 560, 610, 600), fill=accent)


DRAWERS = {
    "classic-cotton-tee": lambda c, m, a: _tee(c, m, a),
    "everyday-hoodie": lambda c, m, a: _tee(c, m, a, hood=True, long_sleeves=True),
    "canvas-cap": _cap,
    "ceramic-mug": _mug,
    "linen-throw-pillow": _pillow,
    "soy-candle": _candle,
    "leather-card-holder": _card_holder,
    "canvas-tote-bag": _tote,
    "steel-water-bottle": _bottle,
}


# Where each object's base sits on the grid, so its shadow touches it.
BASE_Y = {
    "classic-cotton-tee": 770, "everyday-hoodie": 790, "canvas-cap": 590, "ceramic-mug": 730,
    "linen-throw-pillow": 730, "soy-candle": 750, "leather-card-holder": 690, "canvas-tote-bag": 770,
    "steel-water-bottle": 780,
}


def _render(slug, top, bottom):
    main, accent = (_hex(x) for x in PALETTES[slug][2:])
    canvas = _Canvas(top, bottom)
    canvas.shadow(500, BASE_Y.get(slug, 790), 520)
    DRAWERS[slug](canvas, main, accent)
    return canvas.image


def _jpeg(image):
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


def sample_photos(slug):
    """Returns [(jpeg_bytes, alt_suffix), ...] for a seeded product, or [] if unknown."""
    if slug not in PALETTES:
        return []
    top, bottom = (_hex(x) for x in PALETTES[slug][:2])
    px = SIZE * SCALE

    front = _render(slug, top, bottom).resize((SIZE, SIZE), Image.LANCZOS)

    # Closer view on a slightly deeper background, cropped around the object.
    detail_full = _render(slug, _shade(top, 0.96), _shade(bottom, 0.9))
    margin = int(px * 0.17)
    detail = detail_full.crop((margin, margin, px - margin, px - margin)).resize((SIZE, SIZE), Image.LANCZOS)

    return [(_jpeg(front), "front view"), (_jpeg(detail), "close-up")]
