# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio>=1.4", "numpy", "matplotlib"]
# ///
"""Compare one index between two dates over the same AOI.

    uv run compare.py work/pre/NBR.tif work/post/NBR.tif --burn --hotspots work/hotspots.json --out work/compare
    uv run compare.py work/pre/NDVI.tif work/post/NDVI.tif --out work/compare

Default: change = post - pre, with the area that dropped or rose by more than --threshold.

--burn: for NBR, dNBR = pre - post, classified with the USGS FIREMON burn-severity ranges (Key & Benson 2006):
< -0.25 high regrowth, -0.25 to -0.1 low regrowth, -0.1 to 0.1 unburned, 0.1 to 0.27 low, 0.27 to 0.44
moderate-low, 0.44 to 0.66 moderate-high, > 0.66 high severity. The ranges were set for temperate forests;
for tropical peat and plantations treat them as a guide and check the SWIR false-colour images.

The summary splits burned area into "confident" (dNBR >= 0.27, moderate severity and up) and "possible" (low
severity, 0.1-0.27). Haze, drought and harvest also lower NBR by about that much, so the low class alone is not
evidence of fire.

--hotspots: an independent check against NASA FIRMS VIIRS detections (hotspots.py). Only hotspots between the two
scene dates are used (the dates come from the stats.json next to each GeoTIFF). For each one the script looks
within 190 m (half a VIIRS pixel) for a confident burn pixel and reports the share that agree; hotspots on
pixels hidden by cloud or smoke on either date are counted apart.

Pixels that are cloud, shadow or no data on either date are left out, and the share left out is reported.
"""

import argparse
import json
import os

import numpy as np

FIREMON = [  # (lower bound, upper bound, label, colour)
    (-np.inf, -0.25, "high regrowth", "#1a9850"),
    (-0.25, -0.1, "low regrowth", "#91cf60"),
    (-0.1, 0.1, "unburned", "#d9d9d9"),
    (0.1, 0.27, "low severity", "#fee08b"),
    (0.27, 0.44, "moderate-low severity", "#fdae61"),
    (0.44, 0.66, "moderate-high severity", "#f46d43"),
    (0.66, np.inf, "high severity", "#a50026"),
]


def read(path):
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read(1).astype(np.float32), ds.profile


def on_grid(src_path, profile):
    """Read src_path resampled onto profile's grid (the two dates can come from different UTM tiles)."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    out = np.full((profile["height"], profile["width"]), np.nan, dtype=np.float32)
    with rasterio.open(src_path) as ds:
        reproject(
            ds.read(1),
            out,
            src_transform=ds.transform,
            src_crs=ds.crs,
            dst_transform=profile["transform"],
            dst_crs=profile["crs"],
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    return out


def scene_date(tif):
    """The scene date from the stats.json that compute_index.py wrote next to the GeoTIFF."""
    with open(os.path.join(os.path.dirname(os.path.abspath(tif)), "stats.json")) as f:
        return json.load(f)["scene"]["date"]


def check_hotspots(args, diff, profile):
    """Share of VIIRS hotspots between the two scene dates that land within 190 m of a confident burn pixel."""
    from rasterio.transform import rowcol
    from rasterio.warp import transform

    with open(args.hotspots) as f:
        hot = json.load(f)["points"]
    pre_date, post_date = scene_date(args.pre), scene_date(args.post)
    hot = [p for p in hot if pre_date <= p["date"] <= post_date]
    if not hot:
        return {"hotspots_between_dates": 0, "note": f"no hotspots between {pre_date} and {post_date}"}, []
    xs, ys = transform("EPSG:4326", profile["crs"], [p["lng"] for p in hot], [p["lat"] for p in hot])
    rows, cols = rowcol(profile["transform"], xs, ys)
    radius = max(1, round(190 / abs(profile["transform"].a)))
    h, w = diff.shape
    on_burn = hidden = outside = 0
    points = []
    for r, c in zip(rows, cols):
        if not (0 <= r < h and 0 <= c < w):
            outside += 1
            continue
        points.append((r, c))
        win = diff[max(0, r - radius) : r + radius + 1, max(0, c - radius) : c + radius + 1]
        if not np.isfinite(win).any():
            hidden += 1
        elif np.nanmax(win) >= 0.27:
            on_burn += 1
    seen = len(points) - hidden
    return {
        "dates": [pre_date, post_date],
        "hotspots_between_dates": len(hot) - outside,
        "hidden_by_cloud_or_smoke": hidden,
        "visible": seen,
        "on_confident_burn": on_burn,
        "agreement_pct": round(100 * on_burn / seen, 1) if seen else None,
        "radius_m": 190,
    }, points


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pre")
    ap.add_argument("post")
    ap.add_argument("--burn", action="store_true", help="dNBR with FIREMON severity classes (use with NBR)")
    ap.add_argument("--threshold", type=float, default=0.1, help="change counted as a drop or rise (non-burn mode)")
    ap.add_argument("--hotspots", help="hotspots.json from hotspots.py, to check the burn map against (with --burn)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    os.makedirs(args.out, exist_ok=True)
    pre, profile = read(args.pre)
    post = on_grid(args.post, profile)
    both = np.isfinite(pre) & np.isfinite(post)
    res = abs(profile["transform"].a)
    ha_per_px = res * res / 10_000
    name = os.path.splitext(os.path.basename(args.pre))[0]

    if args.burn:
        diff = np.where(both, pre - post, np.nan)
        classes = []
        for lo, hi, label, colour in FIREMON:
            n = int(np.sum(both & (diff >= lo) & (diff < hi)))
            classes.append({"class": label, "dnbr_range": [lo, hi], "pixels": n, "hectares": round(n * ha_per_px, 1)})
        confident = sum(c["hectares"] for c in classes if c["dnbr_range"][0] >= 0.27)
        possible = sum(c["hectares"] for c in classes if c["class"] == "low severity")
        summary = {
            "mode": "dNBR (pre - post)",
            "confident_burned_hectares": round(confident, 1),
            "possible_burned_hectares": round(possible, 1),
            "classes": classes,
        }
        points = []
        if args.hotspots:
            summary["hotspot_check"], points = check_hotspots(args, diff, profile)
        cmap = ListedColormap([c for *_, c in FIREMON])
        norm = BoundaryNorm([-1.0, -0.25, -0.1, 0.1, 0.27, 0.44, 0.66, 2.0], cmap.N)
        fig, ax = plt.subplots(figsize=(7, 7 * pre.shape[0] / max(pre.shape[1], 1) + 0.6), dpi=120)
        ax.imshow(np.ma.masked_invalid(diff), cmap=cmap, norm=norm)
        ax.set_axis_off()
        if points:
            ax.scatter([p[1] for p in points], [p[0] for p in points], s=4, c="#000000", marker="+", linewidths=0.6)
        ax.set_title(
            f"Burn severity (dNBR)  confident ~{confident:,.0f} ha, possible ~{possible:,.0f} ha"
            + ("  (+ = VIIRS hotspots)" if points else ""),
            fontsize=9,
        )
        ax.legend(
            handles=[Patch(color=c, label=label) for *_, label, c in FIREMON],
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            fontsize=8,
            frameon=False,
        )
        fig.savefig(f"{args.out}/dnbr.png", bbox_inches="tight")
        plt.close(fig)
    else:
        diff = np.where(both, post - pre, np.nan)
        drop, rise = both & (diff <= -args.threshold), both & (diff >= args.threshold)
        summary = {
            "mode": f"{name} change (post - pre)",
            "threshold": args.threshold,
            "drop_hectares": round(int(drop.sum()) * ha_per_px, 1),
            "rise_hectares": round(int(rise.sum()) * ha_per_px, 1),
            "mean_change": round(float(np.nanmean(diff)), 4) if both.any() else None,
        }
        lim = float(np.nanpercentile(np.abs(diff), 98)) if both.any() else 1.0
        fig, ax = plt.subplots(figsize=(7, 7 * pre.shape[0] / max(pre.shape[1], 1) + 0.6), dpi=120)
        im = ax.imshow(diff, cmap="RdBu", vmin=-lim, vmax=lim)
        ax.set_axis_off()
        ax.set_title(f"{name} change (post - pre)", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        fig.savefig(f"{args.out}/change.png", bbox_inches="tight")
        plt.close(fig)

    summary.update(
        {
            "index": name,
            "pre": args.pre,
            "post": args.post,
            "res_m": res,
            "aoi_hectares": round(pre.size * ha_per_px, 1),
            "compared_pct": round(100 * float(both.mean()), 1),
            "note": "Pixels cloudy, shadowed or missing on either date are excluded (see compared_pct).",
        }
    )
    with open(f"{args.out}/summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print(json.dumps({k: v for k, v in summary.items() if k != "classes"}, indent=2, default=float))
    if args.burn:
        for c in summary["classes"]:
            print(f"  {c['class']:24} {c['hectares']:>10,.1f} ha")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
