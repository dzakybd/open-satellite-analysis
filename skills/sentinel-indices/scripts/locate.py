# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Turn an address, a latitude and longitude, or a bbox into an AOI file.

    uv run locate.py "Pulang Pisau, Kalimantan Tengah" --buffer-m 3000 --out work/aoi.json
    uv run locate.py --lat -2.95 --lng 114.10 --buffer-m 5000 --out work/aoi.json
    uv run locate.py --bbox 114.0,-3.0,114.2,-2.9 --out work/aoi.json

Geocoding uses OpenStreetMap Nominatim (no key). Its policy allows at most one request per second, so geocode
once and reuse aoi.json.
"""

import argparse
import sys
import urllib.parse

from common import buffer_bbox, http_json, save_json


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="address or place name")
    ap.add_argument("--lat", type=float, help="latitude in degrees, with --lng, instead of a query")
    ap.add_argument("--lng", type=float)
    ap.add_argument("--bbox", help="west,south,east,north in degrees, instead of a query")
    ap.add_argument("--buffer-m", type=float, default=3000, help="half-width of the square AOI around a point")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.bbox:
        w, s, e, n = (float(v) for v in args.bbox.split(","))
        aoi = {"name": args.query or "bbox", "lat": (s + n) / 2, "lng": (w + e) / 2, "bbox": [w, s, e, n]}
    elif args.lat is not None and args.lng is not None:
        lat, lng = args.lat, args.lng
        aoi = {
            "name": args.query or f"{lat},{lng}",
            "lat": lat,
            "lng": lng,
            "bbox": buffer_bbox(lat, lng, args.buffer_m),
        }
    elif args.query:
        q = urllib.parse.urlencode({"q": args.query, "format": "jsonv2", "limit": 1})
        hits = http_json(f"https://nominatim.openstreetmap.org/search?{q}")
        if not hits:
            sys.exit(f"no geocoding result for {args.query!r}; try a simpler place name or give --lat/--lng")
        lat, lng = float(hits[0]["lat"]), float(hits[0]["lon"])
        aoi = {
            "name": hits[0]["display_name"],
            "lat": lat,
            "lng": lng,
            "bbox": buffer_bbox(lat, lng, args.buffer_m),
            "source": "OpenStreetMap Nominatim",
        }
    else:
        sys.exit("give an address, --lat/--lng or --bbox")

    aoi["bbox"] = [round(v, 6) for v in aoi["bbox"]]
    save_json(aoi, args.out)
    print(f"{aoi['name']}\nlat {aoi['lat']:.5f}, lng {aoi['lng']:.5f}  bbox {aoi['bbox']}  -> {args.out}")


if __name__ == "__main__":
    main()
