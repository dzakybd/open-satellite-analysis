---
title: sentinel-indices
emoji: 🛰️
colorFrom: red
colorTo: gray
sdk: static
pinned: false
license: mit
short_description: "Seeing through the karhutla smoke with free satellite data"
---

# sentinel-indices showcase

Ask a question about a place, get an answer from free satellite data. Sentinel-2 and Landsat 8/9 imagery, 245 spectral indices from the Awesome Spectral Indices catalog (computed with spyndex), and a check against NASA FIRMS fire hotspots. No account, no API key.

Precomputed results of [sentinel-indices](https://github.com/dzakybd/sentinel-indices) over a 14 km x 14 km area in Pulang Pisau, Central Kalimantan, during the October 2026 peatland fires, three ways: the scripts on Sentinel-2 (29 Aug vs 21 Oct), the scripts on Landsat 8/9 (25 Aug vs 4 Oct), and the Deep Agents runner (gpt-6-luna) answering the question in plain words. Each view shows the scene in true colour and shortwave infrared, the dNBR burn-severity map, and the hectares. The page calls no model.

Two versions: a skill for coding agents (`npx skills add dzakybd/sentinel-indices`) and a LangChain Deep Agents version for your own agent workflow. The write-up: [dzaky.ai.id/en/blog/sentinel-indices-karhutla](https://dzaky.ai.id/en/blog/sentinel-indices-karhutla).

Contains modified Copernicus Sentinel data 2026 (via Earth Search, Element 84) and Landsat 8/9 data (USGS, via Microsoft Planetary Computer). Fire hotspots: NASA FIRMS. Code: MIT.
