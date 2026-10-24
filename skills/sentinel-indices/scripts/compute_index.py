# /// script
# requires-python = ">=3.10"
# dependencies = ["spyndex>=0.12", "rasterio>=1.4", "numpy", "matplotlib"]
# ///
"""Compute spectral indices (Awesome Spectral Indices, via spyndex) for one scene over the AOI.

    uv run compute_index.py work/aoi.json work/post/scene.json NBR NDVI --out work/post

Works for Sentinel-2 (20 m grid) and Landsat 8/9 (30 m) scenes from find_scene.py. For each index writes
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
