# Social posts (drafts)

Numbers come from `runs/kalteng-2/compare/summary.json` (Pulang Pisau, 29 Aug vs 21 Oct 2026). Image for every post: `docs/assets/pulangpisau-hero.png`. Replace the GitHub link once the repo is public.

## Threads (Indonesian, same shape as the pid-parser post)

> Aku bikin 𝘀𝗲𝗻𝘁𝗶𝗻𝗲𝗹-𝗶𝗻𝗱𝗶𝗰𝗲𝘀, tool open-source yang menjawab pertanyaan soal suatu lokasi dari citra satelit Sentinel-2 gratis. Tanpa API key.
>
> Contohnya karhutla di Pulang Pisau, Kalteng. Citra 21 Oktober kalau dilihat biasa isinya cuma asap. Tapi di band inframerah gelombang pendek (SWIR), bekas terbakar dan garis apinya kelihatan tembus asap.
>
> 𝗖𝗮𝗿𝗮 𝗸𝗲𝗿𝗷𝗮𝗻𝘆𝗮: 1. Alamat atau koordinat diubah jadi area. 2. Cari citra paling bersih untuk area itu, bukan untuk satu tile. 3. Hitung indeks spektral (NBR, NDVI, dan 240+ lainnya) sebelum dan sesudah. 4. Cocokkan dengan hotspot VIIRS NASA.
>
> Hasilnya: sekitar 2.900 ha terbakar dengan keyakinan tinggi, padahal yang terlihat cuma sepertiga area karena asap. 84% hotspot yang terlihat jatuh di area itu.
>
> Jadi pertanyaan seperti "berapa hektar yang terbakar di sini sejak Agustus?" bisa dijawab agent AI pakai data satelit.

## LinkedIn (English)

> The 21 October Sentinel-2 image over Pulang Pisau, Central Kalimantan, shows nothing but smoke. Switch to shortwave infrared and the burn scar and the fire front are right there.
>
> I built open-satellite-analysis, an open-source skill that lets an AI agent answer questions about a place from free satellite data, with no account and no API key:
>
> 1. Address or coordinates → an area of interest
> 2. The clearest Sentinel-2 scene for that area, judged from the cloud mask over the area itself, not the whole 110 km tile (a tile listed at 13.6% cloud had 66% of our area under smoke)
> 3. A spectral index from the Awesome Spectral Indices catalog (245 work on Sentinel-2), computed with spyndex
> 4. Before vs after, as burn severity (dNBR), checked against NASA FIRMS VIIRS hotspots
>
> Result for this site: about 2,900 ha of confident burn, in the third of the area visible through the smoke. 84% of the visible VIIRS hotspots land on it.
>
> Two lessons from building it:
> • Earth Search pixels are already corrected for ESA's 2022 reflectance offset, but the metadata still lists the offset. Apply it again and healthy forest reads as NDVI −0.99.
> • During the peak of the fires, almost every scene of a tile 50 km away was 96–100% cloud for five weeks. The optical satellite waits for the smoke to clear; the heat sensors don't.
>
> It runs as a skill in Claude Code or Codex, or as a LangChain Deep Agent. Same shape as my pid-parser project.
>
> Code: github.com/dzakybd/open-satellite-analysis · Write-up: dzaky.ai.id/en/blog/open-satellite-analysis
>
> #RemoteSensing #Sentinel2 #GeoAI #Karhutla #AIAgents

## X thread (English)

1. Sentinel-2, 21 Oct, Pulang Pisau (Central Kalimantan): true colour is all smoke. Shortwave infrared shows the burn scar and the fire front through it. [image]
2. I built an open-source skill so an AI agent can answer "how much burned here?" from free satellite data. No API key.
3. It picks the clearest scene for your area, not the tile. A tile listed at 13.6% cloud had 66% of our area under smoke.
4. Indices come from the Awesome Spectral Indices catalog via spyndex: NBR for burns, NDVI, NDWI and 240+ more.
5. Result: ~2,900 ha confident burn in the visible third. 84% of visible NASA VIIRS hotspots land on it.
6. Code + write-up: [links]
