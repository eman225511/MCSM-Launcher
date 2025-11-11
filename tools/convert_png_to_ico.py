#!/usr/bin/env python3
"""Small helper to convert a PNG to ICO using Pillow.
Usage: python tools/convert_png_to_ico.py input.png output.ico
"""
import sys
try:
    from PIL import Image
except Exception as e:
    print("Pillow is required to convert PNG to ICO. Install it with: pip install pillow")
    raise

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: convert_png_to_ico.py input.png output.ico")
        sys.exit(2)
    inp = sys.argv[1]
    out = sys.argv[2]
    img = Image.open(inp)
    # Save as ICO with a 256x256 size (suitable for modern Windows icons)
    try:
        img.save(out, format='ICO', sizes=[(256, 256)])
        print(f"Wrote {out}")
    except Exception as e:
        print(f"Failed to write ico: {e}")
        raise
