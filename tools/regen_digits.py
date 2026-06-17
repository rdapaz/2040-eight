#!/usr/bin/env python3
# Redraw the 2040-eight number tiles with clean, rounded-chunky digits.
#
# The sprite data lives in assets/spritesheet.hpp as picosystem color_t values
# (AAAA RRRR GGGG BBBB, byteswapped, 4-bit/channel). We decode that to an image,
# repaint only the 11 number tiles (56x56 grid, top 3 rows), and re-encode — so
# every other pixel (logo, icons, VICTORY) is preserved byte-for-byte.
#
#   python tools/regen_digits.py            # writes out/sheet_preview.png only
#   python tools/regen_digits.py --write    # also rewrites assets/spritesheet.{hpp,png}
import re, sys, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
HPP  = ROOT / "assets" / "spritesheet.hpp"
PNG  = ROOT / "assets" / "spritesheet.png"
PREV = ROOT.parent.parent.parent / "pico_wimbledon" / "out" / "sheet_preview.png"
FONT = "C:/Windows/Fonts/Roboto-Black.ttf"
W, H, T = 224, 336, 56                          # sheet size, tile size

# value -> (col,row) in the 56px grid (matches sprite_col/sprite_row in the game)
TILES = {2:(0,0),4:(1,0),8:(2,0),16:(3,0),32:(0,1),64:(1,1),128:(2,1),
         256:(3,1),512:(0,2),1024:(1,2),2048:(2,2)}

def swap(v): return ((v & 0xff) << 8) | (v >> 8)
def decode(v):
    w = swap(v); return (((w>>8)&0xf)*17, ((w>>4)&0xf)*17, (w&0xf)*17, ((w>>12)&0xf)*17)
def encode(r,g,b,a):
    q=lambda c:(c+8)//17
    return swap((q(a)<<12)|(q(r)<<8)|(q(g)<<4)|q(b))

vals = [int(x,16) for x in re.findall(r"0x[0-9a-fA-F]{4}", HPP.read_text())]
img = Image.new("RGBA",(W,H)); img.putdata([decode(v) for v in vals])

def luminance(c): return 0.299*c[0]+0.587*c[1]+0.114*c[2]

def make_glyph(text, fill, maxw, maxh, blur=6.0, thr=105):
    """Rounded-chunky glyph mask, scaled to fit maxw x maxh, colored `fill`."""
    big = ImageFont.truetype(FONT, 240)
    tmp = Image.new("L",(2000,420),0); d = ImageDraw.Draw(tmp)
    bb = d.textbbox((0,0), text, font=big)
    g = Image.new("L",(bb[2]-bb[0]+60, bb[3]-bb[1]+60),0)
    ImageDraw.Draw(g).text((30-bb[0],30-bb[1]), text, font=big, fill=255)
    g = g.filter(ImageFilter.GaussianBlur(blur))            # soften corners
    g = g.point(lambda p: 255 if p>=thr else 0)             # re-threshold -> rounded + chunky
    g = g.crop(g.getbbox())
    s = min(maxw/g.width, maxh/g.height)
    g = g.resize((max(1,round(g.width*s)), max(1,round(g.height*s))), Image.LANCZOS)
    layer = Image.new("RGBA",(W,H),(0,0,0,0)); return g, layer, fill

for val,(c,r) in TILES.items():
    x0,y0 = c*T, r*T
    bg = img.getpixel((x0+4,y0+4))                          # flat tile colour
    ImageDraw.Draw(img).rectangle([x0,y0,x0+T-1,y0+T-1], fill=bg)
    ink = (40,38,35,255) if luminance(bg) > 150 else (255,255,255,255)
    glyph,_,fill = make_glyph(str(val), ink, T-10, T-14)
    gx = x0 + (T-glyph.width)//2
    gy = y0 + (T-glyph.height)//2
    solid = Image.new("RGBA", glyph.size, fill)
    img.paste(solid, (gx,gy), glyph)

# preview (3x) for review
PREV.parent.mkdir(parents=True, exist_ok=True)
img.convert("RGB").resize((W*3,H*3), Image.NEAREST).save(PREV)
print("wrote preview:", PREV)

if "--write" in sys.argv:
    out = ["const picosystem::color_t spritesheet_data[75264] = {"]
    enc = [encode(*img.getpixel((x,y))) for y in range(H) for x in range(W)]
    for i in range(0,len(enc),8):
        out.append("".join("0x%04x, "%v for v in enc[i:i+8]))
    out.append("")
    out.append("};")
    # preserve the buffer_t the game actually blits from (was at the end of the hpp)
    out.append("picosystem::buffer_t spritesheet_buffer{.w = 224, .h = 336, "
               ".data = (picosystem::color_t *)spritesheet_data};")
    out.append("")
    HPP.write_text("\n".join(out))
    img.convert("RGB").save(PNG)
    print("wrote", HPP, "and", PNG)
