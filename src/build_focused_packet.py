"""
Build a FOCUSED, blinded grading packet from EXISTING reports (no API calls):

  - Indian ABNORMAL cases + matched Western ABNORMAL baseline
  - every model's report per image (so report QUALITY can be compared per model)
  - TB / post-tubercular / Indian-prevalent presentations tagged in the hidden
    key so that subgroup can be analysed separately
  - fully blinded: model + dataset + truth stripped, shuffled, anonymous IDs
  - hidden key written to results/ (NOT inside the packet folder)

The grading interface keeps the full rubric (main finding caught, dangerous
miss, hallucination, overall soundness 1-5) and asks the radiologist to write
their own read first.

USAGE:  python -m src.build_focused_packet reports_<stamp>.json
"""

import re
import sys
import json
import random
import shutil
from pathlib import Path

from .config import RESULTS, DATA_INDIAN, DATA_CHEXPERT
from . import build_grading_packet as bgp

random.seed(13)

PACKET = RESULTS.parent / "grading_packet_focused"

# High-specificity TB / post-tubercular / Indian-prevalent radiographic signs.
TB_PATTERNS = re.compile(
    r"tubercul|post-?primary|miliary|cavit|fibrocavit|tree-?in-?bud|"
    r"granulomat|calcified (?:granulom|node|nodul|lymph|hil)|"
    r"reticulonodular|apical (?:fibrosis|scarring|cavit|thicken|opacit)|"
    r"upper (?:lobe|zone) (?:fibrosis|scarring|cavit|volume loss)|"
    r"fibrotic band|hilar lymphadenopathy",
    re.I,
)
NEG = re.compile(r"no (?:evidence of |findings of |signs of )?(?:tubercul|cavit|miliary|granulom)", re.I)

# Finding categories for like-for-like Indian<->Western matching at analysis time.
CATEGORY_PATTERNS = {
    "consolidation_pneumonia": r"consolidat|pneumonia|airspace opacit",
    "pleural_effusion": r"pleural effusion|costophrenic.*(?:blunt|obscur)|\beffusion\b",
    "cardiomegaly": r"cardiomegaly|enlarged (?:cardiac|heart)|cardiothoracic ratio",
    "edema_congestion": r"edema|oedema|congestion|vascular redistribut",
    "mass_nodule": r"\bmass\b|nodule|nodular opacit|lesion",
    "collapse_atelectasis": r"atelectasis|collapse|volume loss",
    "pneumothorax": r"pneumothorax",
    "opacity_other": r"opacit|infiltrat|reticulonodular",
}
NEG_WORDS = re.compile(r"\b(?:no|without|free of|negative for|absence of|not)\b", re.I)
BOUNDARY = re.compile(r"[.;:]")


def _image(case_id: str, dataset: str) -> Path | None:
    folder = DATA_INDIAN if dataset == "indian" else DATA_CHEXPERT
    p = folder / case_id
    return p if p.exists() else None


def _negated_spans(text: str) -> list[tuple[int, int]]:
    """Each negation word negates from itself to the next clause boundary
    (handles 'no focal consolidation, effusion, or pneumothorax')."""
    spans = []
    for m in NEG_WORDS.finditer(text):
        b = BOUNDARY.search(text, m.end())
        end = b.start() if b else min(len(text), m.end() + 90)
        spans.append((m.start(), end))
    return spans


def _has(text: str, pattern: str) -> bool:
    """True if pattern occurs at least once outside any negated clause."""
    spans = _negated_spans(text)
    for m in re.finditer(pattern, text, re.I):
        if not any(s <= m.start() < e for s, e in spans):
            return True
    return False


def _tb_text(rec: dict) -> bool:
    txt = (rec["report"].get("findings", "") + " " + rec["report"].get("impression", ""))
    return bool(TB_PATTERNS.search(txt)) and not NEG.search(txt)


def _categories(text: str) -> list[str]:
    return [cat for cat, pat in CATEGORY_PATTERNS.items() if _has(text, pat)]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.build_focused_packet reports_<stamp>.json")
        sys.exit(1)
    reports_file = RESULTS / sys.argv[1]
    if not reports_file.exists():
        reports_file = Path(sys.argv[1])
    recs = json.loads(reports_file.read_text())["records"]

    abn = [r for r in recs if (r["truth_label"] or "").lower() == "abnormal"
           and r["dataset"] in ("indian", "western")]

    # image-level TB flag + finding categories, aggregated across all models'
    # reports for the same image (used for matched subgroup analysis later).
    tb_image: dict[tuple, bool] = {}
    cat_image: dict[tuple, set] = {}
    for r in abn:
        key = (r["dataset"], r["case_id"])
        tb_image[key] = tb_image.get(key, False) or _tb_text(r)
        txt = (r["report"].get("findings", "") + " " + r["report"].get("impression", ""))
        cat_image.setdefault(key, set()).update(_categories(txt))

    # build blinded items
    random.shuffle(abn)
    if PACKET.exists():
        shutil.rmtree(PACKET)
    (PACKET / "images").mkdir(parents=True, exist_ok=True)

    key: dict = {}
    items: list = []
    for idx, rec in enumerate(abn):
        src = _image(rec["case_id"], rec["dataset"])
        if not src:
            continue
        blind_id = f"CASE{idx:04d}"
        ext = src.suffix.lower()
        shutil.copy(src, PACKET / "images" / f"{blind_id}{ext}")
        key[blind_id] = {
            "dataset": rec["dataset"],
            "model": rec["model"],
            "model_label": rec["model_label"],
            "model_id": rec["model_id"],
            "case_id": rec["case_id"],
            "truth_label": rec["truth_label"],
            "report_id": rec["report_id"],
            "indian_prevalent_tb": tb_image[(rec["dataset"], rec["case_id"])],
            "finding_categories": sorted(cat_image[(rec["dataset"], rec["case_id"])]),
        }
        items.append({
            "blind_id": blind_id,
            "image": f"images/{blind_id}{ext}",
            "findings": rec["report"].get("findings", ""),
            "impression": rec["report"].get("impression", ""),
        })

    # hidden key in results/, NOT in the packet folder
    stamp = reports_file.stem.replace("reports_", "")
    key_file = RESULTS / f"_key_focused_{stamp}.json"
    key_file.write_text(json.dumps(key, indent=2))

    # reuse the existing blinded HTML/CSV writers, pointed at the focused folder
    bgp.PACKET = PACKET
    bgp._write_csv(items)
    bgp._write_html(items)

    # console summary
    n_in = sum(1 for v in key.values() if v["dataset"] == "indian")
    n_we = sum(1 for v in key.values() if v["dataset"] == "western")
    n_in_tb = sum(1 for v in key.values() if v["dataset"] == "indian" and v["indian_prevalent_tb"])
    n_we_tb = sum(1 for v in key.values() if v["dataset"] == "western" and v["indian_prevalent_tb"])
    print(f"Focused packet built: {PACKET}")
    print(f"  total reports to grade: {len(items)}")
    print(f"  Indian:  {n_in}  (TB/Indian-prevalent: {n_in_tb})")
    print(f"  Western: {n_we}  (TB-like: {n_we_tb})")

    # finding-category distribution (image-level) for matched analysis
    seen: set = set()
    dist: dict = {"indian": {}, "western": {}}
    for v in key.values():
        ik = (v["dataset"], v["case_id"])
        if ik in seen:
            continue
        seen.add(ik)
        for c in (v["finding_categories"] or ["(none detected)"]):
            dist[v["dataset"]][c] = dist[v["dataset"]].get(c, 0) + 1
    print("\n  finding-category distribution (unique images, multi-label):")
    cats = sorted(set(dist["indian"]) | set(dist["western"]))
    print(f"    {'category':<24}{'Indian':>8}{'Western':>9}")
    for c in cats:
        print(f"    {c:<24}{dist['indian'].get(c,0):>8}{dist['western'].get(c,0):>9}")

    print(f"\n  rubric axes: {list(bgp.RUBRIC.keys())}")
    print(f"  hidden key (separate, do NOT share): {key_file}")
    print(f"  packet folder contents: {[p.name for p in sorted(PACKET.iterdir())]}")


if __name__ == "__main__":
    main()
