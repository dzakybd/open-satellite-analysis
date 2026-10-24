# /// script
# requires-python = ">=3.10"
# dependencies = ["spyndex>=0.12"]
# ///
"""Search the Awesome Spectral Indices catalog (via spyndex) for indices that work on Sentinel-2 (or Landsat).

    uv run search_index.py --domain burn
    uv run search_index.py water
    uv run search_index.py NBR --json
    uv run search_index.py --domain burn --platform Landsat-OLI

Prints short name, long name, domain, the bands it needs (catalog names) and the reference. Catalog band names
are not Sentinel-2 band numbers: N = B8 (NIR), N2 = B8A, S1 = B11 (SWIR 1), S2 = B12 (SWIR 2), R = B4, G = B3,
B = B2, RE1-RE3 = B5-B7, A = B1. "S2" means SWIR 2, not Sentinel-2.
"""

import argparse
import json

import spyndex


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyword", nargs="?", help="matched against short name and long name, case-insensitive")
    ap.add_argument("--domain", help="vegetation, water, burn, soil, urban, snow, ...")
    ap.add_argument("--platform", default="Sentinel-2", help="Sentinel-2 or Landsat-OLI (Landsat 8/9)")
    ap.add_argument("--all-platforms", action="store_true", help="include indices the platform cannot compute")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    constants = set(spyndex.constants.keys())
    rows = []
    for name, idx in spyndex.indices.items():
        if args.domain and idx.application_domain != args.domain:
            continue
        if not args.all_platforms and args.platform not in idx.platforms:
            continue
        kw = (args.keyword or "").lower()
        if kw and kw not in name.lower() and kw not in idx.long_name.lower():
            continue
        bands = [b for b in idx.bands if b not in constants]
        rows.append(
            {
                "short_name": name,
                "long_name": idx.long_name,
                "domain": idx.application_domain,
                "bands": bands,
                "sentinel2_bands": [spyndex.bands[b].sentinel2a.band for b in bands if b in spyndex.bands],
                "constants": [b for b in idx.bands if b in constants],
                "formula": idx.formula,
                "reference": idx.reference,
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r['short_name']:10} {r['domain']:10} {r['long_name']}")
        print(f"{'':10} bands {', '.join(r['bands'])} (= {', '.join(r['sentinel2_bands'])})  {r['formula']}")
        print(f"{'':10} {r['reference']}")
    print(f"\n{len(rows)} indices")


if __name__ == "__main__":
    main()
