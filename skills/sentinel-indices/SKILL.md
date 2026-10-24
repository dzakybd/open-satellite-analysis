---
name: sentinel-indices
description: Answer questions about a place on Earth from free Sentinel-2 and Landsat 8/9 satellite imagery and spectral indices (NBR, NDVI, NDWI and 240 more from Awesome Spectral Indices). Geocodes an address, finds the clearest scene near a date, computes indices, compares two dates (burned area, vegetation loss, flooding), checks fires against NASA FIRMS hotspots (VIIRS, MODIS), and suggests other free data (Sentinel-1 radar, elevation) when optical imagery cannot answer. No account or API key. Use when asked what burned, flooded, was cleared, greened or changed at a location, about forest and land fires (karhutla), or to get satellite imagery or an index for an address or coordinates.
---

# Satellite spectral indices (Sentinel-2, Landsat)

Turn a question about a place ("how much burned near Pulang Pisau this fire season?") into numbers and pictures from satellite imagery. Every source is free and needs no key:

- **Imagery:** Sentinel-2 L2A (10-20 m, every ~5 days) from Earth Search, Element 84's STAC API on AWS (the default), and Landsat 8/9 Collection 2 L2 (30 m, every ~8 days with both) from Microsoft Planetary Computer, read with a token its API gives out anonymously (`--source landsat`).
- **Indices:** the [Awesome Spectral Indices](https://github.com/awesome-spectral-indices/awesome-spectral-indices) catalog, computed with [spyndex](https://github.com/awesome-spectral-indices/spyndex).
- **Fire hotspots:** NASA FIRMS VIIRS (375 m, three satellites) and MODIS (1 km), from the public 24 h / 48 h / 7 d files.
- **Geocoding:** OpenStreetMap Nominatim (at most one request per second; geocode once and reuse `aoi.json`).

Scripts live next to this file in `scripts/`. Run them with `uv run` (installs their dependencies on the fly). `SKILL_DIR` below means the directory containing this file, and `WORK` your work directory.

## Choose the data source

Pick by what the question needs. The scripts cover the first four; the last two are free too, and are what to suggest (or fetch with a STAC client or a STAC MCP server) when optical imagery cannot answer.

| Need | Source | Why | Access |
|---|---|---|---|
| Most questions: burns, vegetation, water, soil | **Sentinel-2 L2A** (default) | 10-20 m, every ~5 days, 245 indices | scripts, Earth Search |
| A clear view when Sentinel-2 is cloudy or smoky; history before 2017 | **Landsat 8/9** (`--source landsat`) | different overpass days, 30 m, record back to 2013 (Landsat 5/7 to the 1980s) | scripts, Planetary Computer |
| Is something burning now? when did it start? | **FIRMS VIIRS** (+ `MODIS`) | several passes a day, sees heat through smoke | `hotspots.py` |
| Fire under thick smoke, floods under cloud | **Sentinel-1 radar** (`sentinel-1-rtc`) | radar sees through cloud and smoke; water is dark in VV/VH | not scripted: Planetary Computer STAC, anonymous token |
| Slope, drainage, low-lying (flood-prone, peat) ground | **Copernicus DEM** (`cop-dem-glo-30`) | 30 m elevation | not scripted: Earth Search STAC, no token |

Landsat and Sentinel-1 on Earth Search are in requester-pays buckets (they need AWS credentials and bill the reader); use Planetary Computer for those. When Sentinel-2 is hidden on the date you need, try Landsat on nearby dates before giving up: in the Pulang Pisau run, Sentinel-2 had no clear view in October but Landsat 8 saw the whole area on 4 October.

## 1. Pin the place: `locate.py`

```bash
uv run SKILL_DIR/scripts/locate.py "Pulang Pisau, Kalimantan Tengah" --buffer-m 5000 --out WORK/aoi.json
uv run SKILL_DIR/scripts/locate.py --lat -2.8 --lng 114.05 --buffer-m 7000 --out WORK/aoi.json
uv run SKILL_DIR/scripts/locate.py --bbox 113.98,-2.87,114.12,-2.73 --out WORK/aoi.json
```

Use `--lat/--lng` for coordinates (a negative latitude written as `"-2.8,114.05"` is read as a flag). Keep the AOI small: a few km to ~15 km across. Larger areas are slow to read and blur the answer.

## 2. Pick the index: `search_index.py`

```bash
uv run SKILL_DIR/scripts/search_index.py --domain burn       # vegetation, water, burn, soil, urban, snow
uv run SKILL_DIR/scripts/search_index.py moisture
```

It lists only indices Sentinel-2 can compute (some burn indices need a thermal band it does not have); add `--platform Landsat-OLI` for Landsat, which has no red-edge bands. Defaults that work:

| Question | Index | Read it as |
|---|---|---|
| Burned? how badly? | `NBR` (compare two dates as dNBR) | NBR drops where vegetation burns |
| Vegetation health, clearing | `NDVI` (dense canopy: `EVI`) | ~0.6-0.9 healthy canopy, < 0.2 bare or burned |
| Open water, flooding | `NDWI` (built-up areas: `MNDWI`) | > 0 usually water |
| Bare soil, mining, earthworks | `BI` or `NDBI` | rises on exposed soil |

Catalog band names are not Sentinel-2 band numbers: `N` = B8 (NIR), `N2` = B8A, `S1` = B11 (SWIR 1), **`S2` = B12 (SWIR 2), not "Sentinel-2"**, `R` = B4, `G` = B3, `B` = B2, `RE1`-`RE3` = B5-B7.

## 3. Find a clear scene: `find_scene.py`

```bash
uv run SKILL_DIR/scripts/find_scene.py WORK/aoi.json --max-cloud 20 --out WORK/post/scene.json                                  # latest clear
uv run SKILL_DIR/scripts/find_scene.py WORK/aoi.json --date 2026-08-31 --direction before --max-cloud 5 --out WORK/pre/scene.json
```

Add `--source landsat` for Landsat 8/9. Cloud is judged over the AOI from the scene's cloud mask (Sentinel-2 SCL, Landsat QA_PIXEL), not from the tile's cloud cover: a tile listed at 14% cloud can have 66% of your AOI under smoke. It checks the nearest dates first. Exit code 2 means no scene met `--max-cloud`; scene.json then holds the clearest one it found (`aoi_unusable_pct` says how much is hidden). Decide whether that is good enough, or widen `--days`.

For a before/after pair ("how much burned since August?"):

- **before:** `--date <start of the period> --direction before --max-cloud 5`: a clear scene just ahead of the event. For Indonesian fires, July-August, before the dry-season peak.
- **after:** no `--date` (search back from today) with a looser `--max-cloud 70`. The question is about what happened up to now, so the newest scene that shows part of the AOI beats an older clear one. Do **not** search forward from the start date with `--direction after`: that returns the first clear scene after the start, which can be weeks before the fires you are asked about.
- If find_scene prints `newer scenes skipped`, say which dates were hidden, and consider using the newest one with its `compared_pct`.
- If hotspots fall after the "after" scene, the burn they mark is not in your numbers yet. Say so.

## 4. Compute: `compute_index.py`

```bash
uv run SKILL_DIR/scripts/compute_index.py WORK/aoi.json WORK/post/scene.json NBR NDVI --out WORK/post
```

The scene's source comes from scene.json. Writes `<INDEX>.tif` (20 m Sentinel-2, 30 m Landsat; NaN under cloud, shadow or no data), `<INDEX>.png`, `stats.json` (mean, median, p10, p90, valid share, formula, reference) and two pictures of the scene:

- `true_color.png`: what the eye sees, including smoke and haze.
- `swir_false_color.png` (SWIR 2, NIR, red): shortwave infrared passes through most smoke. Burn scars are dark red-brown, healthy vegetation green, active fire fronts bright orange-red. Look at this one before trusting any fire number.

## 5. Compare two dates: `compare.py`

```bash
uv run SKILL_DIR/scripts/compare.py WORK/pre/NBR.tif WORK/post/NBR.tif --burn --hotspots WORK/hotspots.json --out WORK/compare
uv run SKILL_DIR/scripts/compare.py WORK/pre/NDVI.tif WORK/post/NDVI.tif --threshold 0.15 --out WORK/compare
```

`--burn` computes dNBR (pre - post) and classifies burn severity with the USGS FIREMON ranges (Key & Benson 2006). It reports:

- `confident_burned_hectares`: dNBR >= 0.27 (moderate severity and up).
- `possible_burned_hectares`: low severity, 0.1-0.27. Haze, drought and harvest also lower NBR this much, so do not report it as fire without support from the SWIR image or hotspots.
- `compared_pct`: share of the AOI visible on both dates. A low value means the hectares cover only part of the area; say so.
- `hotspot_check` (with `--hotspots`): the share of VIIRS hotspots between the two dates, on pixels visible on both, that fall within 190 m of a confident burn pixel.

Without `--burn` it reports the area where the index dropped or rose by more than `--threshold`.

Compare two scenes from the same source. Sentinel-2 and Landsat bands differ slightly, so a Sentinel-2 "before" against a Landsat "after" adds a small offset to dNBR; if you must mix them, say so.

## 6. Fire hotspots: `hotspots.py`

```bash
uv run SKILL_DIR/scripts/hotspots.py --aoi WORK/aoi.json --days 7 --out WORK/hotspots.json
uv run SKILL_DIR/scripts/hotspots.py --bbox 108,-4.5,117,2 --days 7 --top 10        # where are fires concentrated?
```

Default sensors are VIIRS on Suomi NPP, NOAA-20 and NOAA-21; add `--sensors ...,MODIS` for the 1 km MODIS detections. Only the last 24 h, 48 h or 7 days are public without a key. A hotspot is a heat signal, not a confirmed fire: gas flares and hot industrial sites also trigger it, and small or under-canopy fires are missed.

## Answering

Give the number, the dates of both scenes, how much of the AOI was visible, and the pictures that support it (`swir_false_color.png`, `compare/dnbr.png`). State the limits that apply:

- Pixels are 20 m: fires or clearings smaller than about half a hectare are not resolved.
- Smoke during active fires can hide the area for weeks; the hotspot data still sees heat through it.
- The FIREMON severity ranges were set for temperate forests. On tropical peat, read them as relative severity and check the SWIR image.
- Index changes show that the surface changed, not why or who caused it. Never attribute a fire to a person or company from these data.
