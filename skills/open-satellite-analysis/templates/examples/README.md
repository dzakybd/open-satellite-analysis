# Card examples

Three complete specs for `scripts/card.py`. Image paths in a spec are relative to the spec, so put the layers next to it. The commands below build the layers each example expects (`WORK` is a run folder, `PARK` an OSM outline as GeoJSON, `ID` the scene/GeoTIFF folders from `find_scene.py` and `compute_index.py`).

**burned-area-id.json**: what burned, as a before → after → result strip (`pair`), with cloud and hotspots

```bash
layers.py photo WORK/aoi.json WORK/pre/scene.json --kind swir --boundary PARK --out card/photo_swir_pre.png
layers.py photo WORK/aoi.json WORK/post/scene.json --kind swir --boundary PARK --out card/photo_swir.png
layers.py mask WORK/post/NBR.tif --all --boundary PARK --color "#dbe8d5" --out card/base.png
layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --nodata --boundary PARK --color "#ccd1db" --out card/cloud.png
layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --drop 0.27 --boundary PARK --color "#ff9e40" --out card/maybe.png
layers.py mask WORK/pre/NBR.tif WORK/post/NBR.tif --drop 0.27 --offset auto --boundary PARK --color "#d71a1a" --out card/sure.png
layers.py points WORK/hotspots.json --grid WORK/post/NBR.tif --boundary PARK --out card/hot.json
```

**land-clearing-near-places-id.json**: (a `pair` of 2016 and 2018 photos) is clearing concentrated near some villages? Needs the same NBR for several years. The bar values come from `layers.py mask YEAR/NBR.tif --below 0.3 --within=LAT,LNG,KM [--outside]` run per year (the "% of the visible" figure).

```bash
layers.py photo WORK/aoi.json WORK/2016/scene.json --kind true --boundary PARK --out card/photo_2016.png
layers.py photo WORK/aoi.json WORK/2018/scene.json --kind true --boundary PARK --out card/photo_2018.png
layers.py mask WORK/2016/NBR.tif --all --within=LAT,LNG,3 --within=LAT2,LNG2,3 --boundary PARK --color "#1d6fd1" --alpha 0.38 --out card/zone.png
layers.py mask WORK/2016/NBR.tif WORK/2018/NBR.tif --drop 0.2 --below 0.3 --within=LAT,LNG,3 --within=LAT2,LNG2,3 --boundary PARK --color "#f97316" --out card/new_zone.png
```

**snow-vs-water-en.json**: the photo, an old test, the better test and the real snow, on a snowy scene (compute `MNDWI` and `NDWI` on the scene first, `--scale 2` makes the pictures sharper)

```bash
layers.py photo WORK/aoi.json WORK/snow/scene.json --kind true --scale 2 --out card/photo_feb.png
layers.py mask WORK/snow/MNDWI.tif --above 0 --color "#2b8cff" --alpha 0.82 --scale 2 --out card/water_old.png
layers.py mask WORK/snow/NDWI.tif --above 0.2 --color "#2b8cff" --alpha 0.82 --scale 2 --out card/water_fixed.png
layers.py mask WORK/snow/MNDWI.tif --above 0.75 --also WORK/snow/NDWI.tif,below,0.2 --color "#a855f7" --alpha 0.85 --scale 2 --out card/snow_real.png
```

Then `card.py card/<name>.json` for the PNG, `--animate` for the GIF and MP4.
