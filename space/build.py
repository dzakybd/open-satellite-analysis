"""Pack the precomputed use-case runs into space/data for the Hugging Face Space.

Every number comes from the run's own summary.json, so nothing is retyped. Seven views: the October 2026 karhutla
near Pulang Pisau on Sentinel-2 and on Landsat, the Deep Agent answering the same question, nickel-mining
expansion at Weda Bay, land clearing in the IKN core, the seasonal Danau Sentarum, and the Feb 2024 Demak flood
from Sentinel-1 radar.

Usage: uv run python space/build.py
"""

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "runs"


def load(path):
    return json.loads((RUNS / path).read_text())


def ha(n):
    return f"{n:,.0f} ha"


def burn_case(cid, title, subtitle, run, sensor, ref, note):
    s = load(f"{run}/compare/summary.json")
    pre, post = load(f"{run}/pre/scene.json"), load(f"{run}/post/scene.json")
    hc = s.get("hotspot_check") or {}
    stats = [
        [ha(s["confident_burned_hectares"]), "confident burn (dNBR ≥ 0.27)"],
        [ha(s["possible_burned_hectares"]), "possible burn (low severity, haze-sensitive)"],
        [f"{s['compared_pct']:.0f}%", "of the area visible on both dates"],
    ]
    if hc.get("visible"):
        stats.append([f"{hc['agreement_pct']}%", f"of {hc['visible']} visible VIIRS hotspots on the burn"])
    return {
        "id": cid,
        "title": title,
        "subtitle": subtitle,
        "sensor": sensor,
        "dates": f"{pre['date']} → {post['date']}",
        "stats": stats,
        "images": [
            [f"{run}/post/swir_false_color.png", "After, SWIR"],
            [f"{run}/post/true_color.png", "After, true colour"],
            [f"{run}/pre/swir_false_color.png", "Before, SWIR"],
            [f"{run}/compare/dnbr.png", "Burn severity (dNBR)"],
        ],
        "table": [[c["class"], f"{c['hectares']:,.1f} ha"] for c in s["classes"]],
        "note": note,
        "refs": ref,
    }


def cover_case(cid, title, subtitle, run, wet, dry, sensor, labels, headline, ref, note, images=None):
    s = load(f"{run}/compare/summary.json")
    a, b = load(f"{run}/{wet}/scene.json"), load(f"{run}/{dry}/scene.json")
    stats = [
        [f"{ha(s['pre_hectares'])} → {ha(s['post_hectares'])}", headline],
        [ha(s["gained_hectares"]), "gained"],
        [ha(s["lost_hectares"]), "lost"],
        [f"{s['compared_pct']:.0f}%", "of the area visible on both dates"],
    ]
    return {
        "id": cid,
        "title": title,
        "subtitle": subtitle,
        "sensor": sensor,
        "dates": f"{a['date']} → {b['date']}",
        "stats": stats,
        "images": images
        or [
            [f"{run}/{wet}/true_color.png", labels[0]],
            [f"{run}/{dry}/true_color.png", labels[1]],
            [f"{run}/compare/cover.png", labels[2]],
        ],
        "table": [],
        "note": note,
        "refs": ref,
    }


CASES = [
    burn_case(
        "karhutla",
        "Forest and land fire",
        "Pulang Pisau, Central Kalimantan",
        "kalteng-2",
        "Sentinel-2, 20 m",
        [
            [
                "Berita Sampit, 4 Oct 2026: BPBD counts 7,083.6 ha burned across the regency (Jabiren Raya 3,338.5 ha).",
                "https://beritasampit.com/2026/10/04/karhutla-pulang-pisau-tembus-tujuh-ribu-hektare-lebih-terluas-di-wilayah-jabiren-raya/",
            ],
            [
                "BMKG, 10 Jun 2026: El Niño persists into early 2027, August 2026 the widest dry-season peak.",
                "https://www.bmkg.go.id/berita/utama/bmkg-puncak-musim-kemarau-agustus-2026-perkuat-kesiapan-hadapi-dampak-el-nino",
            ],
        ],
        "On 21 Oct two thirds of the area is under smoke, so the hectares cover only what the satellite could see. The regency figure is a different scope (whole regency, cumulative to about 4 Oct).",
    ),
    burn_case(
        "karhutla-landsat",
        "Same fire, a second satellite",
        "Pulang Pisau, Central Kalimantan",
        "kalteng-2-landsat",
        "Landsat 8/9, 30 m",
        [
            [
                "Berita Sampit, 4 Oct 2026: 7,083.6 ha across the regency, the same day as this Landsat 8 scene.",
                "https://beritasampit.com/2026/10/04/karhutla-pulang-pisau-tembus-tujuh-ribu-hektare-lebih-terluas-di-wilayah-jabiren-raya/",
            ]
        ],
        "Landsat passed on 4 Oct with the whole area visible. A thin smoke plume is not flagged by Landsat's cloud mask. A 14 km box can only cover part of the regency total, and this one covers a little over half of it.",
    ),
    None,  # the Deep Agent answer, filled below
    cover_case(
        "mining",
        "Mining expansion",
        "Weda Bay, Central Halmahera",
        "weda-bay",
        "pre",
        "post",
        "Sentinel-2, 20 m",
        ["2019", "2026", "Bare ground (NBR < 0.1)"],
        "bare ground (NBR < 0.1)",
        [
            [
                "Climate Rights International, Jan 2024: at least 5,331 ha cleared inside nickel concessions on Halmahera.",
                "https://cri.org/reports/nickel-unearthed/",
            ],
            [
                "Mongabay, 26 Feb 2024: Weda Bay Nickel alone 1,456 ha as of 2022; the IWIP estate about 5,000 ha.",
                "https://news.mongabay.com/2024/02/indonesian-nickel-project-harms-environment-and-human-rights-report-says/",
            ],
        ],
        "The 2019 scene is hazy, which makes vegetation indices read wrongly, so this measures bare ground growing instead. The references cover all Halmahera concessions, a far bigger area than this 8 km box, so they confirm the trend, not the number.",
    ),
    cover_case(
        "clearing",
        "Land clearing for a new capital",
        "Nusantara core area (KIPP), East Kalimantan",
        "ikn-core",
        "pre",
        "post",
        "Sentinel-2, 20 m",
        ["2021", "2026", "Standing vegetation (NBR > 0.3)"],
        "standing vegetation (NBR > 0.3)",
        [
            [
                "iNews, 23 Feb 2022: the core area (KIPP) covers 6,671 ha.",
                "https://www.inews.id/finance/bisnis/kawasan-inti-ikn-seluas-6671-ha-terbagi-menjadi-3-klaster/all",
            ],
            [
                "Kaltimkece, 12 Mar 2024: Otorita says the cleared land was eucalyptus and oil-palm plantation; Forest Watch Indonesia counted 1,663 ha of deforestation from 2022 to June 2023.",
                "https://kaltimkece.id/warta/nusantara/setelah-nasa-rilis-foto-foto-bukaan-lahan-di-ikn-nusantara",
            ],
        ],
        "Clouds hide about a third of the 2021 view. Most of what was lost was plantation, not primary forest. The Forest Watch figure covers a different area and period.",
    ),
    cover_case(
        "lake",
        "A seasonal lake",
        "Danau Sentarum, West Kalimantan",
        "sentarum-landsat",
        "wet",
        "dry",
        "Landsat 8/9, 30 m",
        ["Wet season", "Dry season", "Open water (MNDWI > 0)"],
        "open water (MNDWI > 0)",
        [
            [
                "Mongabay Indonesia, 27 Dec 2012: flooded 9-10 months a year, mostly dry in July-September.",
                "https://mongabay.co.id/2012/12/27/mongabay-travel-danau-sentarum-danau-pasang-surut-terluas-di-asia-tenggara/",
            ],
            [
                "LIPI proceeding, 2017: the lake level changes 3-5 m between the wet and the long dry season.",
                "https://karya.brin.go.id/34148/1/Prosiding_2017_Siti%20Aisyah_89-96.pdf",
            ],
        ],
        "The wet scene is from May, not February: February was too cloudy. It still has clouds, so the wet extent is a lower bound. Flooded forest is counted as water.",
    ),
    cover_case(
        "flood",
        "Flood under cloud",
        "Demak, Central Java",
        "demak",
        "pre",
        "flood",
        "Sentinel-1 RTC, same orbit",
        ["Before (VV, dB)", "During (VV, dB)", "New open water (VV < -15 dB)"],
        "open water (VV < -15 dB)",
        [
            [
                "Metro TV, 8 Feb 2024: the Wulan embankment broke at Ketanjung, Karanganyar, at about 06:00 that day.",
                "https://metrotvnews.com/read/b7WCYq1L-banjir-lumpuhkan-jalur-pantura-demak-kemacetan-mengular-hingga-10-km",
            ],
            [
                "Mongabay Indonesia, 19 Feb 2024: 84,270 people affected, 22,860 displaced (BPBD).",
                "https://mongabay.co.id/2024/02/19/demak-banjir-parah-dan-pemilu-susulan-pesan-ekologis-bagi-presiden-baru/amp/",
            ],
        ],
        "Radar sees only open water: flooded rice, crops and buildings look bright, so this is a lower bound. The during scene is 23 hours after the breach. The other orbit (19 Jan vs 12 Feb) gives a similar answer: about 1,280 ha.",
        images=[
            ["demak/pre/VV_dB.png", "Before, 27 Jan (VV, dB)"],
            ["demak/flood/VV_dB.png", "During, 8 Feb (VV, dB)"],
            ["demak/compare/cover.png", "New open water (VV < -15 dB)"],
        ],
    ),
]


def main():
    data = REPO / "space" / "data"
    shutil.rmtree(data, ignore_errors=True)
    cases = []
    for case in CASES:
        if case is None:
            run = load("agent-pulangpisau-2/run.json")
            answer = (RUNS / "agent-pulangpisau-2" / "answer.md").read_text()
            cases.append(
                {
                    "id": "agent",
                    "title": "Asked in plain words",
                    "subtitle": "A LangChain Deep Agent runs the same scripts",
                    "sensor": run["model"],
                    "dates": "",
                    "stats": [
                        [f"{run['seconds']} s", "end to end"],
                        [str(run["tool_calls"]), "tool calls"],
                        [f"{run['input_tokens'] / 1000:.0f}K", "input tokens"],
                    ],
                    "images": [],
                    "table": [],
                    "answer": answer,
                    "note": "The first run answered the wrong period (it searched forward from 31 Aug and compared against 11 Sep). The skill was changed, and this second run matches the run by hand.",
                    "refs": [],
                }
            )
            continue
        dest = data / case["id"]
        dest.mkdir(parents=True)
        images = []
        for src, label in case["images"]:
            name = src.replace("/", "-")
            shutil.copy(RUNS / src, dest / name)
            images.append([name, label])
        case["images"] = images
        cases.append(case)
    (data / "index.json").write_text(json.dumps(cases, indent=2, allow_nan=False))
    print(f"packed {len(cases)} cases into {data}")


if __name__ == "__main__":
    main()
