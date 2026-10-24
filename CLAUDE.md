# open-satellite-analysis

Address or coordinates + question -> Sentinel-2 scene -> spectral index (spyndex) -> numbers and pictures. Agent skill + Deep Agents runner. Free data, no keys.

## Stack
- Python >= 3.12, uv. Skill scripts are standalone (PEP 723, `uv run`), sharing `scripts/common.py`.
- Data: Earth Search STAC v1 (`sentinel-2-l2a`), Planetary Computer (`landsat-c2-l2`, anonymous SAS token), NASA FIRMS public VIIRS/MODIS CSVs, OSM Nominatim.
- Deep Agents (`deepagents`) on `_ChatOpenAICodex` from `langchain-openai==1.7.2` (ChatGPT sign-in, no API key).

## Commands
- Install: `uv sync`
- Format / lint: `uvx ruff format . && uvx ruff check .`
- Manual chain: see README "The pipeline"; example runs in `runs/kalteng-2`.
- Agent: `uv run python agent/run.py runs/<name> "<question>" --effort low`
- Showcase Space: `uv run python space/build.py`, then `hf upload dzakybd/open-satellite-analysis space . --repo-type space --exclude build.py` (HF_TOKEN from ~/.zshrc)

## Layout
- `skills/open-satellite-analysis/`: the published skill. Keep script dependencies to rasterio, spyndex, NumPy, Matplotlib.
- `agent/run.py`: Deep Agents runner. `runs/`: outputs (GeoTIFFs are git-ignored). `docs/`: post drafts and figures. `space/`: static Hugging Face Space.

## Project Learnings
- Earth Search items with `earthsearch:boa_offset_applied: true` already have the ESA +1000 removed from the pixels, but raster:bands still lists offset -0.1. Do not apply it (SWIR goes negative, forest NDVI reads -0.99).
- Skip multi-band assets when mapping bands: `visual` lists B2/B3/B4 and is 8-bit, so it silently replaces red/green/blue.
- Judge cloud over the AOI with SCL, never by `eo:cloud_cover`: a 13.6% tile had 66% of the AOI under smoke.
- During peak karhutla (mid-Sept to Oct 2026) the Central Kalimantan tiles were 96-100% cloud for weeks; use SWIR false colour and FIRMS hotspots, and report `compared_pct`.
- Low-severity dNBR (0.1-0.27) follows haze too; report only >= 0.27 as confident burn.
- Thin haze is not masked by SCL and drags NDVI/NDWI down: a hazy 2019 Weda Bay scene made NDVI show vegetation gained around new pits, and a smoky dry-season scene made Danau Sentarum show more water than the wet season. NBR did not fix Weda Bay either; measuring bare ground growing (`--below 0.1` on NBR) did. Look at both true-colour images.
- Older Earth Search items (baseline < 04.00) name bands by common name ("nir") with the number only in the description ("NIR 1 (band 8)"); band_asset parses both.
- argparse reads `"-2.8,114.05"` as a flag: use `--lat/--lng`.
