"""Shared helpers for the open-satellite-analysis scripts: HTTP, the AOI file, band reads from Sentinel-2 or Landsat,
cloud masks and PNG output.

Imagery sources, both free without an account:
- sentinel-2: Sentinel-2 L2A (10-20 m, every ~5 days) from Earth Search, Element 84's STAC API on AWS.
- landsat: Landsat 8/9 Collection 2 Level-2 (30 m, every ~8 days with both) from Microsoft Planetary Computer,
  whose files are read with a short-lived token that its API hands out anonymously.
- sentinel-1: Sentinel-1 radar, terrain-corrected (RTC) backscatter at 10 m, from the same Planetary Computer.
  Radar sees through cloud, smoke and darkness, so it has no cloud mask: water is simply dark in VV.
"""

import json
import math
import os
import re
import urllib.request

USER_AGENT = "open-satellite-analysis/0.1 (https://github.com/dzakybd/open-satellite-analysis)"

# Catalog band (Awesome Spectral Indices name) -> Landsat 8/9 asset. spyndex has no Landsat 8/9 band table, and its
# N (near-infrared) is Landsat's B5 'nir08'. Landsat has no red-edge bands, so indices that need RE1-RE3 cannot run.
LANDSAT_BANDS = {"A": "coastal", "B": "blue", "G": "green", "R": "red", "N": "nir08", "S1": "swir16", "S2": "swir22"}

SOURCES = {
    "sentinel-2": {
        "stac": "https://earth-search.aws.element84.com/v1",
        "collection": "sentinel-2-l2a",
        "res": 20,  # the SWIR bands burn indices need are 20 m, so every band is read on a 20 m grid
        "platform": "Sentinel-2",  # name in the index catalog's platforms list
        "query": {},
    },
    "landsat": {
        "stac": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "landsat-c2-l2",
        "res": 30,
        "platform": "Landsat-OLI",
        "query": {"platform": {"in": ["landsat-8", "landsat-9"]}},  # Landsat 7's SLC-off stripes are left out
    },
    "sentinel-1": {
        "stac": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "sentinel-1-rtc",
        "res": 20,  # native 10 m; 20 m keeps a 15 km AOI quick and averages down speckle
        "platform": None,  # radar indices are not in the optical catalog; use VV_dB / VH_dB
        "query": {},
        "radar": True,
    },
}

# Sentinel-2 scene classification (SCL) classes that are not usable ground: no data, saturated, cloud shadow, cloud
# medium and high probability, thin cirrus. Class 2 ("dark area") is kept on purpose: fresh burn scars land there.
SCL_UNUSABLE = (0, 1, 3, 8, 9, 10)
# Landsat QA_PIXEL bits that make a pixel unusable: fill, dilated cloud, cirrus, cloud, cloud shadow.
QA_UNUSABLE_BITS = 0b11111

# Cloud reads straight from the COGs over HTTPS, without listing directories.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")

_tokens = {}


def http_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def http_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode()


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def buffer_bbox(lat, lng, metres):
    """[west, south, east, north] of a square of +-metres around a point."""
    dlat = metres / 111_320
    dlng = metres / (111_320 * max(math.cos(math.radians(lat)), 1e-6))
    return [lng - dlng, lat - dlat, lng + dlng, lat + dlat]


def source_of(scene_or_item):
    """'landsat' or 'sentinel-2' for a scene.json or a STAC item."""
    if "source" in scene_or_item:
        return scene_or_item["source"]
    collection = scene_or_item.get("collection")
    return {"landsat-c2-l2": "landsat", "sentinel-1-rtc": "sentinel-1"}.get(collection, "sentinel-2")


def get_item(scene):
    """The STAC item of a scene.json (from find_scene.py)."""
    src = SOURCES[source_of(scene)]
    return http_json(f"{src['stac']}/collections/{src['collection']}/items/{scene['id']}")


def signed(href):
    """Planetary Computer files need a SAS token in the URL; its API gives one out anonymously, per collection."""
    if ".blob.core.windows.net/" not in href:
        return href
    account = href.split("//")[1].split(".")[0]
    container = href.split(".blob.core.windows.net/")[1].split("/")[0]
    key = (account, container)
    if key not in _tokens:
        url = f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}"
        _tokens[key] = http_json(url)["token"]
    return f"{href}?{_tokens[key]}"


def band_asset(item, catalog_band):
    """Asset key for a catalog band name (N, S2, ...) in this item, or None if the sensor has no such band."""
    if source_of(item) == "landsat":
        key = LANDSAT_BANDS.get(catalog_band)
        return key if key in item["assets"] else None
    import spyndex

    s2 = spyndex.bands[catalog_band].sentinel2a.band if catalog_band in spyndex.bands else None  # e.g. 'B12'
    for key, asset in item["assets"].items():
        bands = asset.get("eo:bands") or []
        # Skip the JPEG2000 copies and multi-band composites: 'visual' is an 8-bit RGB picture that also lists
        # B2/B3/B4, and reading it as red gives values of 0-255 instead of reflectance.
        if key.endswith("-jp2") or len(bands) != 1:
            continue
        name = bands[0].get("name", "")
        if name.startswith("B") and "B" + name[1:].lstrip("0") == s2:  # B08 -> B8, B8A stays B8A
            return key
        # Items processed before baseline 04.00 name bands by common name ("nir") and give the number only in the
        # description, e.g. "NIR 1 (band 8)".
        m = re.search(r"\(band (\w+)\)", bands[0].get("description", ""))
        if m and "B" + m.group(1).lstrip("0") == s2:
            return key
    return None


def aoi_grid(item, bbox):
    """The AOI as a grid in the scene's UTM projection, at the source's resolution:
    (crs, bounds, width, height, transform)."""
    from rasterio.crs import CRS
    from rasterio.transform import from_bounds
    from rasterio.warp import transform_bounds

    res = SOURCES[source_of(item)]["res"]
    code = item["properties"].get("proj:code") or f"EPSG:{item['properties']['proj:epsg']}"
    crs = CRS.from_string(code)
    w, s, e, n = transform_bounds("EPSG:4326", crs, *bbox)
    width, height = max(1, round((e - w) / res)), max(1, round((n - s) / res))
    return crs, (w, s, e, n), width, height, from_bounds(w, s, e, n, width, height)


def read_asset(item, key, bounds, width, height, categorical=False, fill=0):
    """One asset clipped to the AOI grid. Reflectance bands come back as float32 surface reflectance (NaN where
    there is no data); categorical bands (SCL, QA_PIXEL) as integers, with `fill` outside the scene.

    Sentinel-2: since processing baseline 04.00 (Jan 2022) ESA adds 1000 to every L2A value, which raster:bands
    describes as offset -0.1. Earth Search removes that 1000 from the pixels of items marked
    earthsearch:boa_offset_applied but still lists the offset, so applying it again would subtract 0.1 twice (SWIR
    over forest comes out negative). The offset is used only when the item does not say the pixels are corrected.
    Landsat C2 L2: scale 0.0000275 and offset -0.2 from raster:bands, used as given."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds as window_from_bounds

    asset = item["assets"][key]
    with rasterio.open(signed(asset["href"])) as ds:
        window = window_from_bounds(*bounds, transform=ds.transform)
        raw = ds.read(
            1,
            window=window,
            out_shape=(height, width),
            boundless=True,
            fill_value=fill,
            resampling=Resampling.nearest if categorical else Resampling.average,
        )
    if categorical:
        return raw
    rb = (asset.get("raster:bands") or [{}])[0]
    scale, offset, nodata = rb.get("scale", 1.0), rb.get("offset", 0.0), rb.get("nodata", 0)
    if item["properties"].get("earthsearch:boa_offset_applied"):
        offset = 0.0
    out = raw.astype(np.float32) * scale + offset
    out[raw == nodata] = np.nan
    return out


def usable_mask(item, bounds, width, height):
    """True where the pixel is usable: not cloud, cloud shadow, cirrus or outside the scene. For radar there is no
    cloud, so it is only "inside the swath"."""
    import numpy as np

    if source_of(item) == "sentinel-1":
        vv = read_asset(item, "vv", bounds, width, height)
        return np.isfinite(vv) & (vv > 0)  # nodata outside the swath
    if source_of(item) == "landsat":
        qa = read_asset(item, "qa_pixel", bounds, width, height, categorical=True, fill=1)  # bit 0 = fill
        return (qa & QA_UNUSABLE_BITS) == 0
    scl = read_asset(item, "scl", bounds, width, height, categorical=True, fill=0)
    return ~np.isin(scl, SCL_UNUSABLE)


def save_geotiff(array, path, crs, transform):
    import numpy as np
    import rasterio

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(array.astype(np.float32), 1)


def save_png(array, path, cmap="RdYlGn", vmin=None, vmax=None, title=None):

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 6 * array.shape[0] / max(array.shape[1], 1) + 0.6), dpi=120)
    im = ax.imshow(array, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def save_rgb_png(r, g, b, path, title=None, per_channel=False):
    """Three bands as an RGB picture with a 2-98 percentile stretch, so hazy or dark scenes stay readable.
    per_channel stretches each band on its own (for false colour, where the bands have different ranges)."""
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rgb = np.dstack([r, g, b])
    if per_channel:
        lo = np.array([np.nanpercentile(c, 2) if np.isfinite(c).any() else 0 for c in (r, g, b)])
        hi = np.array([np.nanpercentile(c, 98) if np.isfinite(c).any() else 1 for c in (r, g, b)])
    else:
        finite = rgb[np.isfinite(rgb)]
        lo, hi = (np.percentile(finite, 2), np.percentile(finite, 98)) if finite.size else (0, 1)
    rgb = np.clip((rgb - lo) / np.maximum(hi - lo, 1e-6), 0, 1)
    rgb[~np.isfinite(rgb)] = 0
    fig, ax = plt.subplots(figsize=(6, 6 * rgb.shape[0] / max(rgb.shape[1], 1) + 0.4), dpi=120)
    ax.imshow(rgb)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=10)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
