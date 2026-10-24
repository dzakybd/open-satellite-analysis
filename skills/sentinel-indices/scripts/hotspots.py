# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Active-fire hotspots from NASA FIRMS, from the public files that need no key (last 24 h, 48 h or 7 days).

    uv run hotspots.py --aoi work/aoi.json --days 7 --out work/hotspots.json
    uv run hotspots.py --bbox 108,-4.5,117,2 --days 7 --top 10      # densest 0.1-degree cells: where to look
    uv run hotspots.py --aoi work/aoi.json --sensors VIIRS_SNPP,VIIRS_NOAA20,VIIRS_NOAA21,MODIS

Sensors: VIIRS on Suomi NPP, NOAA-20 and NOAA-21 (375 m; the default, all three) and MODIS on Terra and Aqua
(1 km, coarser, but a different overpass time and the longest record). More satellites means more passes a day,
so short fires are less likely to fall between passes.

A hotspot is a heat signal seen from orbit, not a confirmed fire: it also fires on flares and hot industrial
sites, and misses small or under-canopy fires. Use it to find where and when, then measure the burn with
Sentinel-2 (compute_index.py + compare.py).
"""

import argparse
import collections
import csv
import io
import json
import sys

from common import http_text, load_json, save_json

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"
SOURCES = {
    "VIIRS_SNPP": "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_{region}_{window}.csv",
    "VIIRS_NOAA20": "noaa-20-viirs-c2/csv/J1_VIIRS_C2_{region}_{window}.csv",
    "VIIRS_NOAA21": "noaa-21-viirs-c2/csv/J2_VIIRS_C2_{region}_{window}.csv",
    "MODIS": "modis-c6.1/csv/MODIS_C6_1_{region}_{window}.csv",
}
DEFAULT_SENSORS = "VIIRS_SNPP,VIIRS_NOAA20,VIIRS_NOAA21"
WINDOWS = {1: "24h", 2: "48h", 7: "7d"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--aoi", help="aoi.json from locate.py")
    where.add_argument("--bbox", help="west,south,east,north")
    ap.add_argument("--days", type=int, choices=sorted(WINDOWS), default=7)
    ap.add_argument("--region", default="SouthEast_Asia", help="FIRMS region file (SouthEast_Asia covers Indonesia)")
    ap.add_argument("--sensors", default=DEFAULT_SENSORS, help=f"comma-separated, from {', '.join(SOURCES)}")
    ap.add_argument("--top", type=int, help="print the N densest 0.1-degree cells")
    ap.add_argument("--out")
    args = ap.parse_args()

    w, s, e, n = load_json(args.aoi)["bbox"] if args.aoi else [float(v) for v in args.bbox.split(",")]
    points = []
    for source in args.sensors.split(","):
        path = SOURCES[source]
        url = f"{BASE}/{path.format(region=args.region, window=WINDOWS[args.days])}"
        try:
            rows = csv.DictReader(io.StringIO(http_text(url)))
        except OSError as err:  # one satellite's file missing should not stop the other (URLError is an OSError)
            print(f"warning: {source} unavailable ({err})", file=sys.stderr)
            continue
        for r in rows:
            lat, lng = float(r["latitude"]), float(r["longitude"])
            if s <= lat <= n and w <= lng <= e:
                points.append(
                    {
                        "lat": lat,
                        "lng": lng,
                        "date": r["acq_date"],
                        "time_utc": r["acq_time"],
                        "confidence": r.get("confidence"),
                        "frp_mw": float(r["frp"]) if r.get("frp") else None,
                        "daynight": r.get("daynight"),
                        "source": source,
                    }
                )

    by_date = collections.Counter(p["date"] for p in points)
    by_conf = collections.Counter(p["confidence"] for p in points)
    by_sensor = collections.Counter(p["source"] for p in points)
    summary = {
        "bbox": [w, s, e, n],
        "window": WINDOWS[args.days],
        "count": len(points),
        "by_date": dict(sorted(by_date.items())),
        "by_confidence": dict(by_conf),
        "by_sensor": dict(by_sensor),
        "sensors": args.sensors.split(","),
        "note": "Hotspots are heat signals, not confirmed fires. VIIRS pixels are 375 m, MODIS 1 km.",
    }
    if args.top:
        cells = collections.Counter((round(p["lat"], 1), round(p["lng"], 1)) for p in points)
        summary["densest_cells"] = [
            {"lat": la, "lng": lo, "hotspots": c} for (la, lo), c in cells.most_common(args.top)
        ]
    print(json.dumps(summary, indent=2))
    if args.out:
        save_json({**summary, "points": points}, args.out)


if __name__ == "__main__":
    main()
