---
name: open-satellite-analysis
description: Answer questions about a place on Earth from free public satellite data: Sentinel-2 and Landsat 8/9 optical imagery with spectral indices (NBR, NDVI, MNDWI and 240 more from Awesome Spectral Indices), and Sentinel-1 radar for floods. Geocodes an address, finds the clearest scene near a date, computes indices, compares two dates (burned area, bare ground from mining or clearing, seasonal water, flood extent) and checks fires against NASA FIRMS hotspots. No account or API key. Use when asked what burned, flooded, was cleared, greened or changed at a location, about forest and land fires (karhutla), or to get satellite imagery or an index for an address or coordinates.
---

# Satellite spectral indices (Sentinel-2, Landsat)

Turn a question about a place ("how much burned near Pulang Pisau this fire season?") into numbers and pictures from satellite imagery. Every source is free and needs no key:

- **Imagery:** Sentinel-2 L2A (10-20 m, every ~5 days) from Earth Search, Element 84's STAC API on AWS (the default), and Landsat 8/9 Collection 2 L2 (30 m, every ~8 days with both) from Microsoft Planetary Computer, read with a token its API gives out anonymously (`--source landsat`).
- **Indices:** the [Awesome Spectral Indices](https://github.com/awesome-spectral-indices/awesome-spectral-indices) catalog, computed with [spyndex](https://github.com/awesome-spectral-indices/spyndex).
- **Fire hotspots:** NASA FIRMS VIIRS (375 m, three satellites) and MODIS (1 km), from the public 24 h / 48 h / 7 d files.
- **Geocoding:** OpenStreetMap Nominatim (at most one request per second; geocode once and reuse `aoi.json`).

Scripts live next to this file in `scripts/`. Run them with `uv run` (installs their dependencies on the fly). `SKILL_DIR` below means the directory containing this file, and `WORK` your work directory.

## Choose the data source

Pick by what the question needs. The scripts cover all but the last row, which is free too and can be fetched with a STAC client or a STAC MCP server.

| Need | Source | Why | Access |
|---|---|---|---|
| Most questions: burns, vegetation, water, soil | **Sentinel-2 L2A** (default) | 10-20 m, every ~5 days, 245 indices | scripts, Earth Search |
| A clear view when Sentinel-2 is cloudy or smoky; history before 2017 | **Landsat 8/9** (`--source landsat`) | different overpass days, 30 m, record back to 2013 (Landsat 5/7 to the 1980s) | scripts, Planetary Computer |
| Is something burning now? when did it start? | **FIRMS VIIRS** (+ `MODIS`) | several passes a day, sees heat through smoke | `hotspots.py` |
| Floods under cloud, fire-season haze, anything optical cannot see | **Sentinel-1 radar** (`--source sentinel-1`) | radar sees through cloud, smoke and darkness; open water is dark in VV | scripts, Planetary Computer |
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

## Recipes by question

| Question | Steps |
|---|---|
| How much burned? | S2 or Landsat before (clear, before the fire) and after (latest); `compute_index.py ... NBR`; `compare.py ... --burn --hotspots` |
| How much bare ground (mining, clearing, building)? | clear scene per year, same season; `NBR`; `compare.py ... --below 0.1` (bare) and `--above 0.3` (standing vegetation lost) |
| Seasonal water, lake extent | one scene per season; `MNDWI`; `compare.py ... --above 0` (with snow in either scene: `NDWI` and `--above 0.2`, see Snow) |
| Flood | **radar**, same relative orbit, one date just before and one during: `find_scene.py --source sentinel-1 --relative-orbit N`, `compute_index.py ... VV_dB`, `compare.py ... --below -15` |

Use dates a few days to a few weeks apart for change, in the same season, and one source (and for radar one orbit) for both.

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

**Flood mapping with radar.** Open water is dark in VV backscatter, below about -15 dB. `compute_index.py` on a Sentinel-1 scene writes `VV_dB` and `VH_dB` (terrain-corrected, 3 x 3 averaged against speckle), and `compare.py --below -15` on a before and a during scene gives the area that became water. Always pass the same `--relative-orbit` to both `find_scene.py` calls, or the two dates are seen from different angles and the difference means nothing. Radar understates floods: water under rice, crops, trees or buildings looks bright, not dark, so report the hectares as open-water flooding, a lower bound. Check against a permanent-water baseline (rivers, ponds show in both dates).

`--above T` / `--below T` measure a cover class on each date instead of a change: the area where the index is above (or below) T, plus the area gained and lost. Use them for "how much is water / vegetated / bare": `--above 0` on MNDWI or NDWI for open water, `--above 0.3` on NBR for standing vegetation, `--below 0.1` on NBR for bare, mined or burned ground.

**Haze breaks vegetation change.** Thin haze and smoke are often not masked as cloud. They lower vegetation indices over forest, so "vegetation gained" appears wherever the older scene was hazy. In the Weda Bay run, a hazy 2019 scene made both NDVI and NBR report more vegetation in 2026 than in 2019, around new nickel pits. What haze cannot do is make forest look like bare ground, so measure the thing that appears (bare ground with `--below 0.1` on NBR: 146 ha in 2019, 439 ha in 2026, the same trend at three thresholds) rather than the thing that disappears. Look at both `true_color.png` images; if one looks milky, say so, and prefer another date or source.

Compare two scenes from the same source. Sentinel-2 and Landsat bands differ slightly, so a Sentinel-2 "before" against a Landsat "after" adds a small offset to dNBR; if you must mix them, say so.

## 6. Fire hotspots: `hotspots.py`

```bash
uv run SKILL_DIR/scripts/hotspots.py --aoi WORK/aoi.json --days 7 --out WORK/hotspots.json
uv run SKILL_DIR/scripts/hotspots.py --bbox 108,-4.5,117,2 --days 7 --top 10        # where are fires concentrated?
```

Default sensors are VIIRS on Suomi NPP, NOAA-20 and NOAA-21; add `--sensors ...,MODIS` for the 1 km MODIS detections. Only the last 24 h, 48 h or 7 days are public without a key. A hotspot is a heat signal, not a confirmed fire: gas flares and hot industrial sites also trigger it, and small or under-canopy fires are missed.

## 7. Snow, and telling it from water

**`MNDWI` and `NDSI` are the same formula**, (green - SWIR1) / (green + SWIR1), so a water test with `MNDWI > 0` reads snow as water. On a snowy Central Park scene (Sentinel-2, 5 Feb 2026) it called 100% of 15,927 clearly snowy pixels water; Landsat 9 on the same day gave the same picture. Snow and water both reflect green and absorb shortwave infrared. Near-infrared is what separates them: water absorbs it, snow reflects it.

What works, measured on that scene against labels made from visible brightness only (snow: bright in February and land by March; water: dark and permanent), 14,959 water and 15,927 snow pixels:

| Test | Water found | Snow called water |
|---|---|---|
| `MNDWI > 0` | 100% | 100% |
| `MNDWI > 0` and NIR (B8) < 0.11 | 100% | 0% |
| `NDWI > 0.2` (`(G - NIR) / (G + NIR)`) | 99.5% | 0% |
| `--mask-snow` on `compute_index.py` (drops snow by ESA's SCL class 11, Landsat's QA snow bit) | 99.9% | 0.9% |

Ranked by separability (AUC), NDWI, the NIR band, the blue band and SWIR1 reflectance all score above 0.99; `MNDWI` scores 0.88, and the `AWEIsh`, `AWEInsh` and `WI2015` water indices score near 0 (they rate snow as more water-like than water). So in a scene with snow, map water with `NDWI` and a threshold near 0.2, or add `--mask-snow` (and say how much was masked). `NDSI` itself is the right index for mapping snow. Limits: one scene, one city, easy cases (clearly bright against clearly dark): thin snow, ice-covered lakes and shadowed urban pixels were not tested, and NDWI > 0.2 does flag some building shadows. Radar was not tested.

## 8. Make a share card (picture, GIF, video)

For a post or a comment, turn a result into one picture that a person who does not work with satellite data can read in five seconds: a plain-language question as the headline, two or three big numbers, a photo next to the result drawn on it, a legend, and one honest sentence about the limits. The design is an HTML template (`templates/card.html`), rendered by Chrome, so it looks like a designed page, not a plot.

```bash
uv run SKILL_DIR/scripts/layers.py photo WORK/aoi.json WORK/post/scene.json --kind swir --boundary PARK.geojson --out WORK/card/photo.png
uv run SKILL_DIR/scripts/layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --drop 0.27 --offset auto --boundary PARK.geojson --color "#d71a1a" --out WORK/card/burn.png
uv run SKILL_DIR/scripts/layers.py points WORK/hotspots.json --grid WORK/post/NBR.tif --boundary PARK.geojson --out WORK/card/hot.json
uv run SKILL_DIR/scripts/card.py WORK/card/card.json                 # the picture
uv run SKILL_DIR/scripts/card.py WORK/card/card.json --animate       # plus a GIF and an MP4
```

`layers.py` makes a satellite photo (`--kind true` or `swir`) and flat-colour masks that are transparent elsewhere (`--above`, `--below`, `--also PATH,above|below,T` for a second GeoTIFF, `--drop`, `--nodata`, `--all`, limited to a park outline with `--boundary` or to a disc around a place with `--within=LAT,LNG,KM`), and prints the hectares and share each mask covers: use those numbers on the card. `card.py` reads a JSON spec (copy one from `templates/examples/`, which also lists the layer commands for each): `kicker`, `title` (`*words*` get the accent colour), `stats` (big numbers, optionally counting up), `rows` of cells (`panel` with stacked `layers` and a `legend`, `pair` for a before → after strip in one bordered card with a date `chip` on each of its `frames`, `stat`, `bars`, `label`, `text`; a panel or pair can `crop` to part of the picture), `note`, `footer`. With `at: [start, end]` times, `--animate` reveals layers (`fade`, `down`, `right`, `scan-right`), counts numbers up, pops hotspots and grows bars. It needs Google Chrome (driven by Playwright, nothing to download) and ffmpeg.

Rules that made the cards readable: say what the colours mean in words, and no index names in the headline; show what a test called water or burned *on the photo*, not on a grey grid; put the hectares as football fields when it helps; count hotspots inside the boundary only (`layers.py points` prints how many of the total fall inside); put the headline and photo at time 0, because feeds show only the first frame of a GIF; end on the limits (cloud share, pixel size, what the data cannot say). Check the picture before posting, and for a GIF that a feed may show as a still, post the MP4 instead.

## Answering

Give the number, the dates of both scenes, how much of the AOI was visible, and the pictures that support it (`swir_false_color.png`, `compare/dnbr.png`). State the limits that apply:

- Pixels are 20 m: fires or clearings smaller than about half a hectare are not resolved.
- Smoke during active fires can hide the area for weeks; the hotspot data still sees heat through it.
- The FIREMON severity ranges were set for temperate forests. On tropical peat, read them as relative severity and check the SWIR image.
- Index changes show that the surface changed, not why or who caused it. Never attribute a fire to a person or company from these data.
