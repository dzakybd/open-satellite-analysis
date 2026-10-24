**Question:** How much land burned this fire season within about 7 km of -2.8, 114.05 in Pulang Pisau, Central Kalimantan, since the end of August 2026? Check the burn map against this week's fire hotspots.

**Estimated burned area: 176.8 ha** of confident burn, plus **35.4 ha of possible low-severity change** in the ~7 km-radius area. The comparison covers **99.9% of the AOI**.

- **Scenes:** Sentinel-2 NBR, 29 August 2026 and 11 September 2026. The estimate is the change between those scenes; it does **not** establish that all change occurred after the end of August.
- **Hotspot check:** NASA FIRMS VIIRS found **1,412 hotspots in the AOI during 17–23 October 2026**. These are later than the image comparison, so they cannot validate the mapped burn: there were no hotspots within the comparison dates.
- **Supporting files:** `runs/agent-pulangpisau/compare/dnbr.png` and the post-scene `runs/agent-pulangpisau/post/swir_false_color.png`; scene dates and coverage are recorded in the `pre/scene.json`, `post/scene.json`, and `compare` output files.

**Limits:** burn estimates are based on 20 m pixels; smaller burns may not be resolved. Smoke, drought, or harvesting can affect index changes. FIREMON severity thresholds are not calibrated for tropical peat, so treat severity as relative. VIIRS hotspots are heat signals, not confirmed fires, and may miss small or under-canopy fires.
