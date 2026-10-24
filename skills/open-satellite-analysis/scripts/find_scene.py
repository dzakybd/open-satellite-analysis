# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio>=1.4", "numpy"]
# ///
"""Find the clearest scene over an AOI near a date, from Sentinel-2 (default) or Landsat 8/9.

    uv run find_scene.py work/aoi.json --out work/post/scene.json                      # latest clear scene
    uv run find_scene.py work/aoi.json --date 2026-06-30 --direction before --out work/pre/scene.json
    uv run find_scene.py work/aoi.json --source landsat --out work/post-landsat/scene.json

Cloud is judged over the AOI, not the whole scene: for each candidate the cloud mask (Sentinel-2 SCL, Landsat
QA_PIXEL) is read for the AOI only, and the scene counts as clear when enough of the AOI is usable ground. Scene
cloud cover (eo:cloud_cover) is only a cheap pre-filter. Thin smoke is often not flagged as cloud, so look at the
pictures from compute_index.py before trusting a scene taken during an active fire.
"""

import argparse
import datetime as dt
import sys

import numpy as np
from common import SOURCES, aoi_grid, http_json, load_json, save_json, usable_mask


def search(source, bbox, start, end, max_tile_cloud, relative_orbit=None):
    src = SOURCES[source]
    query = {"eo:cloud_cover": {"lte": max_tile_cloud}, **src["query"]} if not src.get("radar") else {}
    if relative_orbit is not None:
        query["sat:relative_orbit"] = {"eq": relative_orbit}
    items, url, body = (
        [],
        f"{src['stac']}/search",
        {
            "collections": [src["collection"]],
            "bbox": bbox,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "query": query,
            "limit": 100,
        },
    )
    while url and len(items) < 300:
        page = http_json(url, body)
        items += page.get("features", [])
        nxt = next((link for link in page.get("links", []) if link.get("rel") == "next"), None)
        url, body = (nxt["href"], nxt.get("body")) if nxt else (None, None)
    return items


def clear_fraction(item, bbox):
    """Share of the AOI that is usable ground in this scene (0-1). Outside the scene counts as not usable."""
    _, bounds, width, height, _ = aoi_grid(item, bbox)
    return float(usable_mask(item, bounds, width, height).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aoi")
    ap.add_argument("--source", choices=sorted(SOURCES), default="sentinel-2")
    ap.add_argument(
        "--relative-orbit",
        type=int,
        help="Sentinel-1 only: keep one relative orbit, so two dates are seen from the same angle (needed for change)",
    )
    ap.add_argument("--date", help="target date YYYY-MM-DD (default today)")
    ap.add_argument("--direction", choices=["before", "after", "nearest"], default="before")
    ap.add_argument("--days", type=int, default=90, help="how far from --date to search")
    ap.add_argument("--max-cloud", type=float, default=20, help="max %% of the AOI that may be cloud or no data")
    ap.add_argument("--max-checks", type=int, default=12, help="candidates whose cloud mask is read, nearest first")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    aoi = load_json(args.aoi)
    target = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    span = dt.timedelta(days=args.days)
    start = target - span if args.direction != "after" else target
    end = target + span if args.direction != "before" else target
    items = search(args.source, aoi["bbox"], start, end, max_tile_cloud=95, relative_orbit=args.relative_orbit)
    if not items:
        sys.exit(f"no {args.source} scenes between {start} and {end} over this AOI")

    def date_of(it):
        return dt.date.fromisoformat(it["properties"]["datetime"][:10])

    items.sort(key=lambda it: (abs((date_of(it) - target).days), it["properties"].get("eo:cloud_cover", 100)))
    best, checked = None, []
    for it in items[: args.max_checks]:
        clear = clear_fraction(it, aoi["bbox"])
        p = it["properties"]
        checked.append((it["id"], str(date_of(it)), p.get("eo:cloud_cover"), round(100 * (1 - clear), 1)))
        print(
            f"  {it['id']}  {date_of(it)}  tile cloud {p.get('eo:cloud_cover') or 0:5.1f}%  AOI unusable {100 * (1 - clear):5.1f}%"
        )
        if best is None or clear > best[1]:
            best = (it, clear)
        if 100 * (1 - clear) <= args.max_cloud:
            best = (it, clear)
            break

    it, clear = best
    p = it["properties"]
    src = SOURCES[args.source]
    scene = {
        "source": args.source,
        "id": it["id"],
        "datetime": p["datetime"],
        "date": str(date_of(it)),
        "platform": p.get("platform"),
        "orbit": f"{p.get('sat:orbit_state', '')}-{p.get('sat:relative_orbit', '')}" if src.get("radar") else None,
        "tile": p.get("grid:code", "").replace("MGRS-", "")
        or (f"{p.get('landsat:wrs_path', '')}/{p.get('landsat:wrs_row', '')}" if not src.get("radar") else "radar"),
        "tile_cloud_pct": p.get("eo:cloud_cover"),
        "aoi_unusable_pct": round(100 * (1 - clear), 1),
        "meets_max_cloud": 100 * (1 - clear) <= args.max_cloud,
        "target_date": str(target),
        "stac_item": f"{src['stac']}/collections/{src['collection']}/items/{it['id']}",
        "checked": [{"id": c[0], "date": c[1], "tile_cloud_pct": c[2], "aoi_unusable_pct": c[3]} for c in checked],
    }
    # Newer scenes passed over for cloud: for an "after" image the newest view, even partly hidden, may matter more.
    scene["newer_scenes_skipped"] = [c for c in scene["checked"] if c["date"] > scene["date"]]
    save_json(scene, args.out)
    if scene["newer_scenes_skipped"]:
        skipped = ", ".join(f"{c['date']} ({c['aoi_unusable_pct']}% unusable)" for c in scene["newer_scenes_skipped"])
        print(f"note: newer scenes skipped for cloud: {skipped}")
    flag = "" if scene["meets_max_cloud"] else f"  (no scene met --max-cloud {args.max_cloud}; this is the clearest)"
    print(f"{scene['id']}  {scene['date']}  tile {scene['tile']}  AOI unusable {scene['aoi_unusable_pct']}%{flag}")
    if not scene["meets_max_cloud"]:
        sys.exit(2)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
