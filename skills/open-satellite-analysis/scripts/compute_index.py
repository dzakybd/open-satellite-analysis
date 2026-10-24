# /// script
# requires-python = ">=3.10"
# dependencies = ["spyndex>=0.12", "rasterio>=1.4", "numpy", "matplotlib"]
# ///
"""Compute spectral indices (Awesome Spectral Indices, via spyndex) for one scene over the AOI.

    uv run compute_index.py work/aoi.json work/post/scene.json NBR NDVI --out work/post

Works for Sentinel-2 (20 m grid) and Landsat 8/9 (30 m) scenes from find_scene.py. For a Sentinel-1 radar scene
the "indices" are VV_dB and VH_dB: terrain-corrected backscatter in decibels (10 log10 of the linear power),
averaged 3 x 3 to calm speckle. Open water is dark in VV (below about -15 dB); see compare.py --below. For each index writes
<INDEX>.tif (float32, NaN where cloud, shadow or no data), <INDEX>.png and an entry in stats.json. Always writes
two pictures of the scene: true_color.png (what the eye sees: smoke, haze) and swir_false_color.png (SWIR 2, NIR,
red: shortwave infrared passes through most smoke; burn scars show dark red-brown, healthy vegetation green and
active fire fronts bright orange-red). Bands are converted to surface reflectance, which the formulas expect.
"""

import argparse
import sys

import numpy as np
import spyndex
from common import (
    SOURCES,
    aoi_grid,
    band_asset,
    get_item,
    load_json,
    read_asset,
    save_geotiff,
    save_json,
    save_png,
    save_rgb_png,
    usable_mask,
)

RADAR_BANDS = {"VV_dB": "vv", "VH_dB": "vh"}


def box_mean(a, size=3):
    """Mean over a size x size window, ignoring NaN (a cheap speckle filter, no SciPy needed)."""
    pad = size // 2
    p = np.pad(a, pad, constant_values=np.nan)
    stack = [p[i : i + a.shape[0], j : j + a.shape[1]] for i in range(size) for j in range(size)]
    with np.errstate(all="ignore"):
        return np.nanmean(np.stack(stack), axis=0)


def radar(args, aoi, scene):
    """VV_dB / VH_dB for a Sentinel-1 RTC scene."""
    unknown = [i for i in args.indices if i not in RADAR_BANDS]
    if unknown:
        sys.exit(f"{unknown}: Sentinel-1 scenes support {list(RADAR_BANDS)}")
    item = get_item(scene)
    crs, bounds, width, height, transform = aoi_grid(item, aoi["bbox"])
    stats = {
        "scene": {k: scene.get(k) for k in ("source", "id", "date", "platform", "orbit", "aoi_unusable_pct")},
        "aoi": aoi,
        "grid": {"crs": str(crs), "res_m": SOURCES["sentinel-1"]["res"], "width": width, "height": height},
    }
    for name in args.indices:
        lin = read_asset(item, RADAR_BANDS[name], bounds, width, height)
        lin[lin <= 0] = np.nan
        lin = box_mean(lin)
        with np.errstate(all="ignore"):
            db = (10 * np.log10(lin)).astype(np.float32)
        db[~np.isfinite(db)] = np.nan
        save_geotiff(db, f"{args.out}/{name}.tif", crs, transform)
        finite = db[np.isfinite(db)]
        save_png(
            db,
            f"{args.out}/{name}.png",
            cmap="gray",
            vmin=-25,
            vmax=0,
            title=f"{name}  {scene['date']}  {scene.get('orbit')}",
        )
        stats[name] = {
            "long_name": f"Sentinel-1 RTC {RADAR_BANDS[name].upper()} backscatter, dB",
            "valid_pct": round(100 * finite.size / db.size, 1),
            "mean": round(float(finite.mean()), 2) if finite.size else None,
            "p10": round(float(np.percentile(finite, 10)), 2) if finite.size else None,
            "p90": round(float(np.percentile(finite, 90)), 2) if finite.size else None,
            "below_minus15_pct": round(100 * float((finite < -15).mean()), 1) if finite.size else None,
        }
        print(
            f"{name}: mean {stats[name]['mean']} dB  p10 {stats[name]['p10']}  below -15 dB {stats[name]['below_minus15_pct']}%"
        )
    save_json(stats, f"{args.out}/stats.json")
    print(f"-> {args.out}/ (GeoTIFF, PNG, stats.json)")


# Colour maps: burn indices drop where it burned, so red = low reads as "burned" like the vegetation maps.
CMAP = {"water": "Blues", "burn": "RdYlGn", "vegetation": "RdYlGn", "soil": "YlOrBr", "urban": "magma"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aoi")
    ap.add_argument("scene")
    ap.add_argument("indices", nargs="+", help="short names from search_index.py, e.g. NBR NDVI NDWI")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    aoi, scene = load_json(args.aoi), load_json(args.scene)
    if scene.get("source") == "sentinel-1":
        return radar(args, aoi, scene)
    unknown = [i for i in args.indices if i not in spyndex.indices]
    if unknown:
        sys.exit(f"unknown index {unknown}; find names with search_index.py")
    source = scene.get("source", "sentinel-2")
    platform = SOURCES[source]["platform"]
    unsupported = [i for i in args.indices if platform not in spyndex.indices[i].platforms]
    if unsupported:
        sys.exit(f"{unsupported} cannot be computed from {source} (they need a band it does not have)")

    item = get_item(scene)
    crs, bounds, width, height, transform = aoi_grid(item, aoi["bbox"])
    valid = usable_mask(item, bounds, width, height)

    cache = {}

    def band(catalog_name):
        """Catalog band name (N, S2, ...) -> reflectance array on the AOI grid."""
        if catalog_name not in cache:
            key = band_asset(item, catalog_name)
            if key is None:
                sys.exit(f"{source} has no band for catalog band {catalog_name}")
            cache[catalog_name] = read_asset(item, key, bounds, width, height)
        return cache[catalog_name]

    stats_path = f"{args.out}/stats.json"
    try:
        stats = load_json(stats_path)
    except FileNotFoundError:
        stats = {}
    stats["scene"] = {k: scene.get(k) for k in ("source", "id", "date", "platform", "tile", "aoi_unusable_pct")}
    stats["aoi"] = aoi
    stats["grid"] = {"crs": str(crs), "res_m": SOURCES[source]["res"], "width": width, "height": height}

    for name in args.indices:
        idx = spyndex.indices[name]
        params = {}
        for b in idx.bands:
            params[b] = spyndex.constants[b].default if b in spyndex.constants else band(b)
        values = np.asarray(spyndex.computeIndex(name, params=params), dtype=np.float32)
        values[~valid | ~np.isfinite(values)] = np.nan
        save_geotiff(values, f"{args.out}/{name}.tif", crs, transform)
        finite = values[np.isfinite(values)]
        lo, hi = np.percentile(finite, [2, 98]) if finite.size else (0, 1)
        save_png(
            values,
            f"{args.out}/{name}.png",
            cmap=CMAP.get(idx.application_domain, "viridis"),
            vmin=lo,
            vmax=hi,
            title=f"{name} ({idx.long_name})  {scene['date']}",
        )
        stats[name] = {
            "long_name": idx.long_name,
            "domain": idx.application_domain,
            "formula": idx.formula,
            "reference": idx.reference,
            "valid_pct": round(100 * finite.size / values.size, 1),
            "mean": round(float(finite.mean()), 4) if finite.size else None,
            "median": round(float(np.median(finite)), 4) if finite.size else None,
            "p10": round(float(np.percentile(finite, 10)), 4) if finite.size else None,
            "p90": round(float(np.percentile(finite, 90)), 4) if finite.size else None,
        }
        print(f"{name}: mean {stats[name]['mean']}  median {stats[name]['median']}  valid {stats[name]['valid_pct']}%")

    save_rgb_png(band("R"), band("G"), band("B"), f"{args.out}/true_color.png", title=f"True colour  {scene['date']}")
    save_rgb_png(
        band("S2"),
        band("N"),
        band("R"),
        f"{args.out}/swir_false_color.png",
        title=f"SWIR false colour (SWIR 2, NIR, red)  {scene['date']}  {scene.get('platform') or source}",
        per_channel=True,
    )
    save_json(stats, stats_path)
    print(f"-> {args.out}/ (GeoTIFF, PNG, stats.json, true_color.png, swir_false_color.png)")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
