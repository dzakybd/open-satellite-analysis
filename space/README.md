---
title: open-satellite-analysis
emoji: 🛰️
colorFrom: red
colorTo: gray
sdk: static
pinned: false
license: mit
short_description: "Five places in Indonesia, from free satellite data"
---

# open-satellite-analysis showcase

Ask a question about a place, get an answer from free public satellite data. Sentinel-2, Landsat 8/9 and Sentinel-1 radar, 245 published spectral indices (computed with spyndex), and NASA FIRMS fire hotspots. No account and no API key.

Five cases in Indonesia, each checked against news and reports: the October 2026 fires in Pulang Pisau (on Sentinel-2, on Landsat, and answered by a Deep Agent), nickel-mine expansion at Weda Bay, land clearing in the new capital's core area, the seasonal Danau Sentarum, and the February 2024 Demak flood from radar. Each view shows the scenes, the map, the hectares and the sources. The page calls no model.

Two versions: a skill for coding agents (`npx skills add dzakybd/open-satellite-analysis`) and a LangChain Deep Agents version for your own agent workflow. Code: [github.com/dzakybd/open-satellite-analysis](https://github.com/dzakybd/open-satellite-analysis). The write-up: [dzaky.ai.id/en/blog/open-satellite-analysis](https://dzaky.ai.id/en/blog/open-satellite-analysis).

Contains modified Copernicus Sentinel data 2019-2026 (via Earth Search, Element 84, and Microsoft Planetary Computer) and Landsat 8/9 data (USGS). Fire hotspots: NASA FIRMS. Code: MIT.
