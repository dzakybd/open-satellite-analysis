# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio>=1.4", "numpy", "matplotlib", "spyndex"]
# ///
"""Clean map layers for share cards: a satellite photo, and transparent colour masks to stack on it.

    uv run layers.py photo WORK/aoi.json WORK/post/scene.json --kind swir --boundary park.geojson --out WORK/card/photo.png
    uv run layers.py mask WORK/post/NBR.tif --below 0.1 --color "#8c510a" --out WORK/card/bare.png
    uv run layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --drop 0.27 --offset auto --color "#d71a1a" --out WORK/card/burn.png
    uv run layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --nodata --color "#ccd1db" --out WORK/card/cloud.png
    uv run layers.py mask WORK/a/NBR.tif WORK/b/NBR.tif --drop 0.2 --below 0.3 --within=-1.9,103.26,3 --out WORK/card/near.png
    uv run layers.py points WORK/hotspots.json --grid WORK/post/NBR.tif --boundary park.geojson --out WORK/card/hot.json

`photo` writes the scene as a picture: --kind true (what the eye sees) or swir (SWIR 2, NIR, red: sees through
smoke, burn scars show red-purple). `mask` writes one flat colour where a condition holds, transparent elsewhere, so
that card.py can stack and reveal them over the photo. `points` turns FIRMS hotspots into positions on that same
picture. --boundary (GeoJSON, e.g. a park outline from OSM) clips everything to the outline and makes the rest
transparent; the area figures printed then count only inside it.

mask conditions (combine freely, all must hold): --above T / --below T on the last GeoTIFF; --drop T on two
(pre - post >= T, on pixels visible on both dates); or alone --nodata for pixels hidden by cloud on any given
GeoTIFF, --all for the whole area. --within=LAT,LNG,KM limits a mask to a disc around a place (--outside: the rest),
for "is it concentrated near X?" questions. --also PATH,above|below,T (repeatable) adds a test on another GeoTIFF
of the same grid, e.g. snow = NDSI above 0.4 and NDWI below 0.2. The printed percentages are of the whole area and of what was visible.
--offset subtracts a constant from the drop first; `auto` uses the median drop over the AOI, which removes the
haze that lowers every pixel a little (it assumes most of the AOI did not change; check the number it prints).
Use the same --scale for photo and masks so that they line up.
"""

import argparse
import json
import sys

import numpy as np
from common import aoi_grid, band_asset, get_item, load_json, read_asset

BANDS = {"true": ("R", "G", "B"), "swir": ("S2", "N", "R")}


def clip_mask(boundary, crs, transform, shape):
    """True inside the GeoJSON outline (everything, if there is none), on the given grid."""
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom

    if not boundary:
        return np.ones(shape, bool)
    with open(boundary) as f:
        gj = json.load(f)
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
    geoms = [transform_geom("EPSG:4326", crs, (f.get("geometry") or f)) for f in feats]
    return ~geometry_mask(geoms, shape, transform)


def read_tif(path):
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read(1).astype("float64"), ds.crs, ds.transform


def save_rgba(rgba, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.imsave(path, np.clip(rgba, 0, 1))


def photo(args):
    from rasterio.transform import from_bounds

    item = get_item(load_json(args.scene))
    crs, bounds, w, h, _ = aoi_grid(item, load_json(args.aoi)["bbox"])
    W, H = w * args.scale, h * args.scale
    rgb = np.dstack([read_asset(item, band_asset(item, b), bounds, W, H) for b in BANDS[args.kind]])
    inside = clip_mask(args.boundary, crs, from_bounds(*bounds, W, H), (H, W))
    seen = inside & np.isfinite(rgb).all(-1)
    if args.kind == "swir":  # bands have different ranges: stretch each on its own
        lo = np.array([np.percentile(rgb[..., i][seen], 2) for i in range(3)])
        hi = np.array([np.percentile(rgb[..., i][seen], 98) for i in range(3)])
    else:
        lo, hi = np.percentile(rgb[seen], 2), np.percentile(rgb[seen], 98)
    rgb = np.clip((rgb - lo) / np.maximum(hi - lo, 1e-6), 0, 1) ** args.gamma
    save_rgba(np.dstack([np.nan_to_num(rgb), seen.astype(float)]), args.out)
    print(f"{args.kind} photo {W}x{H} -> {args.out}")


def hex_rgb(color):
    c = color.lstrip("#")
    return [int(c[i : i + 2], 16) / 255 for i in (0, 2, 4)]


def near_mask(places, crs, transform, shape):
    """True within km of any (lat, lng, km) place."""
    from rasterio.warp import transform as reproject

    rows, cols = np.indices(shape)
    X, Y = transform * (cols + 0.5, rows + 0.5)
    near = np.zeros(shape, bool)
    for lat, lng, km in places:
        x, y = reproject("EPSG:4326", crs, [lng], [lat])
        near |= np.hypot(X - x[0], Y - y[0]) <= km * 1000
    return near


def mask(args):
    arrays = [read_tif(p) for p in args.tifs]
    a, crs, T = arrays[-1]  # --above / --below read the last GeoTIFF (the later date)
    px_ha = abs(T.a * T.e) / 1e4
    inside = clip_mask(args.boundary, crs, T, a.shape)
    if args.within:
        near = near_mask(args.within, crs, T, a.shape)
        inside &= ~near if args.outside else near
    seen = np.logical_and.reduce([np.isfinite(x) for x, _, _ in arrays])
    conditions = [args.above is not None, args.below is not None, args.drop is not None]
    note = ""
    if args.nodata:
        hit = inside & ~seen
    elif not any(conditions):
        if not args.all:
            sys.exit("give at least one of --above, --below, --drop, --nodata, --all")
        hit = inside
    else:
        hit = inside & seen
        if args.drop is not None:
            if len(arrays) != 2:
                sys.exit("--drop needs two GeoTIFFs: pre then post")
            d = arrays[0][0] - arrays[1][0]
            off = float(np.median(d[inside & seen])) if args.offset == "auto" else float(args.offset or 0)
            note = f" (offset {off:.3f})" if off else ""
            hit &= d - off >= args.drop
        for path, op, t in args.also or []:
            b = read_tif(path)[0]
            hit &= (b > t) if op == "above" else (b < t)
        if args.above is not None:
            hit &= a > args.above
        if args.below is not None:
            hit &= a < args.below
    out = np.zeros(a.shape + (4,))
    out[hit] = hex_rgb(args.color) + [args.alpha]
    if args.scale > 1:
        out = np.kron(out, np.ones((args.scale, args.scale, 1)))
    save_rgba(out, args.out)
    visible = (inside & seen).sum()
    share = f"{100 * hit.sum() / inside.sum():.2f}% of the area"
    if any(conditions):  # a share of what was visible only means something when the condition needs valid pixels
        share += f", {100 * hit.sum() / max(visible, 1):.2f}% of the {visible * px_ha:,.0f} ha visible"
    print(f"mask {hit.sum() * px_ha:,.1f} ha = {share}{note} -> {args.out}")


def points(args):
    from rasterio.warp import transform

    hs = load_json(args.hotspots)["points"]
    a, crs, T = read_tif(args.grid)
    inside = clip_mask(args.boundary, crs, T, a.shape)
    xs, ys = transform("EPSG:4326", crs, [p["lng"] for p in hs], [p["lat"] for p in hs])
    xy = []
    for x, y in zip(xs, ys):
        col, row = ~T * (x, y)
        if 0 <= row < a.shape[0] and 0 <= col < a.shape[1] and inside[int(row), int(col)]:
            xy.append([round(100 * col / a.shape[1], 2), round(100 * row / a.shape[0], 2)])
    with open(args.out, "w") as f:
        json.dump(xy, f)
    print(f"{len(xy)} of {len(hs)} hotspots fall inside the area -> {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("photo")
    p.add_argument("aoi")
    p.add_argument("scene")
    p.add_argument("--kind", choices=sorted(BANDS), default="true")
    p.add_argument("--gamma", type=float, default=0.85, help="below 1 brightens dark scenes")
    p.add_argument("--scale", type=int, default=1, help="read at this multiple of the source grid, for a sharper card")
    p.add_argument("--boundary")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=photo)

    p = sub.add_parser("mask")
    p.add_argument("tifs", nargs="+")
    p.add_argument("--above", type=float)
    p.add_argument("--below", type=float)
    p.add_argument("--drop", type=float)
    p.add_argument("--offset", help="number, or auto (see above); with --drop")
    p.add_argument("--nodata", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--color", default="#d71a1a")
    p.add_argument("--alpha", type=float, default=1.0)
    p.add_argument("--scale", type=int, default=1)
    p.add_argument("--boundary")
    p.add_argument(
        "--within",
        action="append",
        type=lambda v: tuple(float(x) for x in v.split(",")),
        help="LAT,LNG,KM: only within KM of this place (repeat for several; write --within=-1.9,103.2,3, with the =)",
    )
    p.add_argument(
        "--also",
        action="append",
        type=lambda v: (v.split(",")[0], v.split(",")[1], float(v.split(",")[2])),
        help="PATH,above|below,T: also require this test on another GeoTIFF of the same grid",
    )
    p.add_argument("--outside", action="store_true", help="with --within: the rest of the area instead")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=mask)

    p = sub.add_parser("points")
    p.add_argument("hotspots")
    p.add_argument("--grid", required=True, help="any GeoTIFF of the run: its grid is what the photo shows")
    p.add_argument("--boundary")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=points)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
