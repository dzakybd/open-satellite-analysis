# open-satellite-analysis

Ask a question about a place, get an answer from free satellite data. Give an address or coordinates and a question ("how much burned here this fire season?"). The skill finds the clearest Sentinel-2 or Landsat 8/9 scene over that exact area, picks a spectral index from the [Awesome Spectral Indices](https://github.com/awesome-spectral-indices/awesome-spectral-indices) catalog (245 that work on Sentinel-2), computes it with [spyndex](https://github.com/awesome-spectral-indices/spyndex), compares dates, and checks fires against NASA FIRMS hotspots (VIIRS and MODIS). No account, no API key, no GPU.

![Pulang Pisau, Central Kalimantan, 21 Oct 2026: smoke in true colour, the burn scar in shortwave infrared, and the dNBR burn-severity map with VIIRS hotspots](docs/assets/pulangpisau-hero.png)

Two versions, like [pid-parser](https://github.com/dzakybd/pid-parser):

1. **A skill for coding agents** (Claude Code, Codex and others that load `SKILL.md` skills): `npx skills add dzakybd/open-satellite-analysis`
2. **A LangChain Deep Agents version** you can run in your own agent workflow (`agent/run.py`)

See the Pulang Pisau runs (Sentinel-2, Landsat and the Deep Agent's answer), no install needed: [huggingface.co/spaces/dzakybd/open-satellite-analysis](https://huggingface.co/spaces/dzakybd/open-satellite-analysis). The write-up, step by step: [dzaky.ai.id/en/blog/open-satellite-analysis](https://dzaky.ai.id/en/blog/open-satellite-analysis).

Useful for: measuring burned area during forest and land fires (karhutla), checking whether a plot was cleared or burned after a cutoff date, mapping flood extent, tracking crop or forest health, watching bare soil spread around a mine, and giving an agent numbers and pictures instead of raw tiles.

## What it adds over a STAC search

Open MCP servers for STAC already search and download Sentinel-2 scenes. This skill covers the steps after the download, where agents tend to go wrong:

- **Cloud judged over your area, not the tile.** It reads the scene classification layer (SCL) for the AOI only. In the Pulang Pisau run, a scene listed at 13.6% cloud had 66% of the AOI under smoke.
- **The right bands for the question.** The catalog maps each index to its bands; `search_index.py` lists only indices Sentinel-2 can compute and warns that catalog `S2` means SWIR 2, not Sentinel-2.
- **Correct reflectance.** Earth Search pixels are already corrected for the 2022 ESA offset (`earthsearch:boa_offset_applied`) while the metadata still lists it. Applying it again pushes SWIR negative and turns forest NDVI into -0.99.
- **Pictures that see through smoke.** Every scene also gets a SWIR false-colour image (B12, B8, B4), where burn scars and fire fronts show through smoke.
- **An independent check.** `compare.py --burn --hotspots` reports how many VIIRS fire detections land on the burn map.
- **A second satellite when the first is blind.** When smoke hides Sentinel-2, `--source landsat` tries Landsat 8/9 on other days. The skill also tells the agent which free source fits a question it cannot answer optically (Sentinel-1 radar through smoke and cloud, Copernicus DEM for terrain).

## Data sources

| Source | Resolution / revisit | Access | In the scripts |
|---|---|---|---|
| Sentinel-2 L2A | 10-20 m, ~5 days | Earth Search (AWS), no key | yes (default) |
| Landsat 8/9 C2 L2 | 30 m, ~8 days with both | Planetary Computer, anonymous token | yes (`--source landsat`) |
| FIRMS VIIRS (S-NPP, NOAA-20, NOAA-21), MODIS | 375 m / 1 km, several passes a day | public 24 h / 48 h / 7 d files | yes (`hotspots.py`) |
| Sentinel-1 RTC (radar) | 10 m, ~6-12 days, sees through cloud and smoke | Planetary Computer, anonymous token | suggested by the skill, not scripted yet |
| Copernicus DEM | 30 m elevation | Earth Search, no key | suggested by the skill, not scripted yet |

Landsat and Sentinel-1 are also on Earth Search, but in requester-pays buckets that need AWS credentials, so the skill reads them from Planetary Computer.

## Install the skill

```bash
npx skills add dzakybd/open-satellite-analysis
```

Or copy `skills/open-satellite-analysis/` into your harness's skills folder. The scripts run with `uv run` and install their own dependencies (rasterio, spyndex, NumPy, Matplotlib).

## The pipeline

| Step | Script | Output |
|---|---|---|
| 1. Pin the place | `locate.py` (Nominatim, or `--lat/--lng`, or `--bbox`) | `aoi.json` |
| 2. Pick an index | `search_index.py --domain burn` | catalog entries with bands and references |
| 3. Find a clear scene | `find_scene.py` (Sentinel-2 SCL or Landsat QA_PIXEL over the AOI) | `scene.json` |
| 4. Compute | `compute_index.py` (spyndex) | `<INDEX>.tif/.png`, `stats.json`, `true_color.png`, `swir_false_color.png` |
| 5. Compare dates | `compare.py --burn` (dNBR, USGS FIREMON classes) | `dnbr.png`, `summary.json` (confident and possible hectares) |
| 6. Fire hotspots | `hotspots.py` (NASA FIRMS VIIRS + MODIS, last 24 h / 48 h / 7 d) | `hotspots.json` |

## Deep Agents runner (ChatGPT sign-in)

```bash
uv sync
# once: sign in with your ChatGPT account (no API key)
uv run python -c "from langchain_openai.chatgpt_oauth import login_chatgpt; login_chatgpt()"

uv run python agent/run.py runs/my-question \
  "How much land burned this fire season within about 7 km of -2.8, 114.05 in Pulang Pisau, Central Kalimantan, since the end of August 2026?"
```

The agent loads the same `SKILL.md`, runs the scripts in the work directory, and writes `answer.md` and `run.json` (time, tool calls, tokens).

## Example: Pulang Pisau, Central Kalimantan, October 2026

The densest cluster of VIIRS hotspots in Indonesia in the week of 17-23 October 2026 was in Pulang Pisau regency, on peatland. Run by hand with the skill's scripts (`runs/kalteng-2`):

| | |
|---|---|
| AOI | 14 km x 14 km around -2.8, 114.05 (19,602 ha) |
| Before | 29 Aug 2026, tile 49MHS, 0% of the AOI unusable |
| After | 21 Oct 2026, 66% of the AOI under smoke or cloud (tile listed at 13.6%) |
| Visible on both dates | 33.9% of the AOI |
| Confident burn (dNBR >= 0.27) | ~2,925 ha |
| Possible burn (low severity) | ~1,508 ha |
| VIIRS hotspots 17-21 Oct, visible | 318, of which 266 (83.6%) within 190 m of a confident burn pixel |

The hectares cover only the third of the area the satellite could see through the smoke; the real burned area is larger. The hotspot check used the Suomi NPP and NOAA-20 files downloaded on 24 October 2026.

Landsat fills the gap (`runs/kalteng-2-landsat`). Landsat 8 passed on 4 October with 0% of the AOI masked: a smoke plume in true colour, and in SWIR the burn scar with a fire front glowing at its southern edge.

| Landsat 8/9 | |
|---|---|
| Before / after | 25 Aug 2026 (Landsat 9) / 4 Oct 2026 (Landsat 8), 30 m |
| Visible on both dates | 100% of the AOI |
| Confident burn (dNBR >= 0.27) | ~4,003 ha |
| Possible burn (low severity) | ~2,561 ha |

The thin plume is not flagged by Landsat's cloud mask, so pixels under it carry some smoke; SWIR is affected least.

A second site about 50 km to the northeast (`runs/kalteng`, around -2.5, 114.4, the densest hotspot cell that week with 2,226 detections) shows the limit: from mid-September to 24 October every Sentinel-2 scene of its tile reports 96-100% cloud, the haze from the fires themselves, except 1 October (69%), which is usable but hazy. The hotspots see the heat; the optical imagery waits for the smoke to clear.

## Limits

- 20 m pixels: fires or clearings under about half a hectare are not resolved.
- Smoke during active fires can hide an area for weeks. Landsat on other days, hotspots and (not yet scripted) Sentinel-1 radar are the ways around it.
- FIREMON severity ranges come from temperate forests; on tropical peat read them as relative severity and check the SWIR image.
- FIRMS public files cover only the last 7 days without a key.
- Index changes show that the surface changed, not why or who caused it.

## Data and licences

- Sentinel-2 L2A: Copernicus Sentinel data, via Earth Search (Element 84) on the AWS Registry of Open Data.
- Landsat 8/9 Collection 2 Level-2: USGS, via Microsoft Planetary Computer.
- Spectral indices: Awesome Spectral Indices catalog and spyndex (Montero et al., 2023, *Scientific Data*).
- Fire hotspots: NASA FIRMS, VIIRS 375 m (Suomi NPP, NOAA-20, NOAA-21) and MODIS 1 km.
- Geocoding: OpenStreetMap Nominatim, © OpenStreetMap contributors.
- Burn severity classes: Key & Benson (2006), FIREMON Landscape Assessment.

Code: MIT.
