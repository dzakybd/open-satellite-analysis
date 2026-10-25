# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.45"]
# ///
"""Render a share card (a PNG for a post or comment, optionally an animated GIF and MP4) from a JSON spec.

    uv run card.py WORK/card/card.json                 # -> WORK/card/card.png
    uv run card.py WORK/card/card.json --animate       # -> also card.gif and card.mp4

The design lives in ../templates/card.html: a kicker, a headline, a strip of big numbers, rows of map panels
(a photo plus transparent layers from layers.py, a legend), bar charts and a short note. The spec only holds the
content. See ../templates/examples/ for two complete specs (a burned-area card and a snow-versus-water card) and
SKILL.md ("Make a share card") for the fields.

Image paths in the spec are relative to the spec file. A points layer takes "src": "hot.json" (from layers.py points).
Every `at: [start, end]` in the spec is a time in seconds for --animate: panels reveal (fade, down, right,
scan-right), numbers count up, legend entries and notes appear. A spec without any `at` is a still card.
The still PNG always shows the finished card. Make frame 0 informative (put the headline and photo at time 0): feeds
show only the first frame before a GIF plays.

Needs Google Chrome (it is driven through Playwright, no browser download) and, for --animate, ffmpeg.
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "templates" / "card.html"


def resolve(spec, base):
    """Make image paths absolute file URLs and inline points files, so the page can load them from anywhere."""
    for row in spec.get("rows", []):
        for cell in row.get("cells", []):
            for panel in [cell, *cell.get("frames", [])]:  # a "pair" cell holds its panels in `frames`
                for layer in panel.get("layers", []):
                    src = layer.get("src")
                    if not src:
                        continue
                    path = (base / src).resolve()
                    if layer.get("kind") == "points":
                        layer["xy"] = json.loads(path.read_text())
                    else:
                        layer["src"] = path.as_uri()
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", help="output path without extension (default: next to the spec)")
    ap.add_argument("--animate", action="store_true", help="also write .gif and .mp4")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--gif-width", type=int, default=720, help="GIF width in pixels (the MP4 keeps the full size)")
    ap.add_argument(
        "--scale", type=float, default=2, help="pixel density of the PNG (2 = 2160 px wide for a 1080 card)"
    )
    args = ap.parse_args()

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    spec_path = pathlib.Path(args.spec).resolve()
    spec = resolve(json.loads(spec_path.read_text()), spec_path.parent)
    out = pathlib.Path(args.out).resolve() if args.out else spec_path.with_suffix("")
    w, h = spec.get("size", [1080, 1350])
    work = pathlib.Path(tempfile.mkdtemp(prefix="osa-card-"))
    page_file = work / "card.html"
    page_file.write_text(TEMPLATE.read_text().replace("__SPEC__", json.dumps(spec)))

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except PlaywrightError as e:
            sys.exit(f"could not start Google Chrome through Playwright: {e}")
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=args.scale)
        page.goto(page_file.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_function("[...document.images].every(i => i.complete)")
        page.wait_for_timeout(800)
        page.screenshot(path=f"{out}.png")
        print(f"{out}.png")

        if args.animate:
            duration = page.evaluate("window.DURATION")
            if not duration:
                sys.exit("--animate needs `at` times in the spec")
            if not shutil.which("ffmpeg"):
                sys.exit("--animate needs ffmpeg on the PATH")
            page.close()
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            page.goto(page_file.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_function("[...document.images].every(i => i.complete)")
            page.wait_for_timeout(800)
            frames = work / "frames"
            frames.mkdir()
            n = int(duration * args.fps)
            for i in range(n):
                page.evaluate(f"setT({i / args.fps})")
                page.screenshot(path=str(frames / f"f{i:04d}.png"))
            pattern = str(frames / "f%04d.png")
            run = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", pattern]
            subprocess.run(
                run + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", f"{out}.mp4"],
                check=True,
            )
            palette = "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
            subprocess.run(
                run + ["-vf", f"scale={args.gif_width}:-1:flags=lanczos,{palette}", "-loop", "0", f"{out}.gif"],
                check=True,
            )
            print(f"{out}.gif, {out}.mp4  ({n} frames, {duration:g} s)")
        browser.close()
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
