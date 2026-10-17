"""
Build the TB-prioritized PILOT grading packet from EXISTING reports (no API calls):

  - 20 Indian abnormal + 20 Western abnormal, Claude Opus 4.8 ONLY
  - effusion (primary) capped at 4; TB / Indian-prevalent presentations prioritized
  - Western finding-matched to Indian where possible (looser match allowed for TB)
  - fully blinded: model + dataset + truth stripped, shuffled, anonymous IDs
  - full rubric + radiologist's own read first
  - hidden key (with TB + finding tags) written to results/, NOT in the packet

Indian finding-type is Claude-text SCAFFOLDING only (not a rigorous label); the
radiologist's blind reads become the true Indian labels for any future version.

USAGE:  python -m src.build_pilot_packet reports_<stamp>.json
"""

import sys
import json
import random
import shutil
from pathlib import Path
from collections import defaultdict

from .config import RESULTS, DATA_INDIAN, DATA_CHEXPERT
from .build_focused_packet import _categories, _tb_text
from .score_western import load_chexpert_labels, md5
from . import build_grading_packet as bgp

random.seed(23)
PACKET = RESULTS.parent / "grading_packet_pilot"

PRIORITY = [
    "pneumothorax", "pleural_effusion", "consolidation_pneumonia",
    "mass_nodule", "cardiomegaly", "edema_congestion",
    "collapse_atelectasis", "opacity_other",
]
CHEX_MAP = {
    "Pneumothorax": "pneumothorax", "Pleural Effusion": "pleural_effusion",
    "Consolidation": "consolidation_pneumonia", "Pneumonia": "consolidation_pneumonia",
    "Lung Lesion": "mass_nodule", "Cardiomegaly": "cardiomegaly",
    "Enlarged Cardiomediastinum": "cardiomegaly", "Edema": "edema_congestion",
    "Atelectasis": "collapse_atelectasis", "Lung Opacity": "opacity_other",
}
RELATED = {
    "opacity_other": ["opacity_other", "consolidation_pneumonia", "mass_nodule", "collapse_atelectasis"],
    "mass_nodule": ["mass_nodule", "opacity_other", "consolidation_pneumonia"],
    "consolidation_pneumonia": ["consolidation_pneumonia", "opacity_other", "collapse_atelectasis"],
    "pleural_effusion": ["pleural_effusion", "opacity_other"],
    "cardiomegaly": ["cardiomegaly", "edema_congestion", "opacity_other"],
    "collapse_atelectasis": ["collapse_atelectasis", "opacity_other", "consolidation_pneumonia"],
    "edema_congestion": ["edema_congestion", "cardiomegaly", "opacity_other"],
    "pneumothorax": ["pneumothorax", "opacity_other"],
}
EFF_CAP = 4
TARGET = 20


def _primary(cats: set) -> str:
    for c in PRIORITY:
        if c in cats:
            return c
    return "opacity_other"


def _select(recs: list) -> tuple[list, dict]:
    """Returns (pairs, claude_by_case). pairs: list of dicts with indian/western
    case ids, finding categories, match exactness, and tb flag."""
    claude_abn = [r for r in recs if r["model"] == "claude"
                  and (r["truth_label"] or "").lower() == "abnormal"]
    claude_by_case = {(r["dataset"], r["case_id"]): r for r in claude_abn}

    # image-level TB flag across all 3 models (select India-specific images)
    tb_image = defaultdict(bool)
    for r in recs:
        if r["dataset"] == "indian" and (r["truth_label"] or "").lower() == "abnormal":
            tb_image[r["case_id"]] |= _tb_text(r)

    indian = {}
    for r in claude_abn:
        if r["dataset"] != "indian":
            continue
        txt = r["report"].get("findings", "") + " " + r["report"].get("impression", "")
        indian[r["case_id"]] = {"primary": _primary(set(_categories(txt))),
                                "tb": tb_image[r["case_id"]]}

    labels = load_chexpert_labels()
    cx_hash = {p.name: md5(p) for p in DATA_CHEXPERT.glob("cx_*.jpg")}
    western = {}
    for r in claude_abn:
        if r["dataset"] != "western":
            continue
        row = labels.get(cx_hash.get(r["case_id"]))
        cats = {cat for col, cat in CHEX_MAP.items()
                if row and (row.get(col, "") or "").strip() in ("1", "1.0")}
        western[r["case_id"]] = _primary(cats)

    # select 20 Indian: TB first, cap effusion, then diversify, then effusion
    selected, eff = [], 0

    def add(cid):
        nonlocal eff
        selected.append(cid)
        if indian[cid]["primary"] == "pleural_effusion":
            eff += 1

    def ok(cid):
        return not (indian[cid]["primary"] == "pleural_effusion" and eff >= EFF_CAP)

    for c in [c for c in indian if indian[c]["tb"]]:
        if len(selected) >= TARGET:
            break
        if ok(c):
            add(c)
    for cat in ["mass_nodule", "consolidation_pneumonia", "opacity_other",
                "collapse_atelectasis", "cardiomegaly"]:
        for c in indian:
            if len(selected) >= TARGET:
                break
            if c not in selected and not indian[c]["tb"] and indian[c]["primary"] == cat:
                add(c)
    for c in indian:
        if len(selected) >= TARGET:
            break
        if c not in selected and ok(c):
            add(c)

    # match each Indian to a distinct Western (scarcest category first)
    avail = defaultdict(list)
    for cid, cat in western.items():
        avail[cat].append(cid)
    west_count = {k: len(v) for k, v in avail.items()}
    pairs = []
    for cid in sorted(selected, key=lambda c: west_count.get(indian[c]["primary"], 0)):
        cat = indian[cid]["primary"]
        chosen, exact = None, None
        for i, rcat in enumerate(RELATED.get(cat, [cat])):
            if avail.get(rcat):
                chosen, exact = avail[rcat].pop(0), (i == 0)
                break
        if not chosen:
            for rcat, lst in avail.items():
                if lst:
                    chosen, exact = lst.pop(0), False
                    break
        pairs.append({
            "indian": cid, "western": chosen,
            "indian_finding": cat, "western_finding": western.get(chosen),
            "exact_match": exact, "indian_prevalent_tb": indian[cid]["tb"],
        })
    return pairs, claude_by_case


def _image(case_id: str, dataset: str) -> Path | None:
    folder = DATA_INDIAN if dataset == "indian" else DATA_CHEXPERT
    p = folder / case_id
    return p if p.exists() else None


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.build_pilot_packet reports_<stamp>.json")
        sys.exit(1)
    reports_file = RESULTS / sys.argv[1]
    if not reports_file.exists():
        reports_file = Path(sys.argv[1])
    recs = json.loads(reports_file.read_text())["records"]

    pairs, claude_by_case = _select(recs)

    # flatten to one grading item per (image, claude report); attach match meta
    flat = []
    for p in pairs:
        for ds, cid in (("indian", p["indian"]), ("western", p["western"])):
            rec = claude_by_case[(ds, cid)]
            flat.append((rec, p))

    random.shuffle(flat)
    if PACKET.exists():
        shutil.rmtree(PACKET)
    (PACKET / "images").mkdir(parents=True, exist_ok=True)

    key, items = {}, []
    for idx, (rec, pinfo) in enumerate(flat):
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
            "indian_prevalent_tb": pinfo["indian_prevalent_tb"],
            "pair_indian_finding": pinfo["indian_finding"],
            "pair_western_finding": pinfo["western_finding"],
            "pair_exact_match": pinfo["exact_match"],
            "matched_with": pinfo["western"] if rec["dataset"] == "indian" else pinfo["indian"],
        }
        items.append({
            "blind_id": blind_id,
            "image": f"images/{blind_id}{ext}",
            "findings": rec["report"].get("findings", ""),
            "impression": rec["report"].get("impression", ""),
        })

    stamp = reports_file.stem.replace("reports_", "")
    key_file = RESULTS / f"_key_pilot_{stamp}.json"
    key_file.write_text(json.dumps(key, indent=2))

    bgp.PACKET = PACKET
    bgp._write_csv(items)
    bgp._write_html(items)

    n_in = sum(1 for v in key.values() if v["dataset"] == "indian")
    n_we = sum(1 for v in key.values() if v["dataset"] == "western")
    n_tb = sum(1 for v in key.values() if v["dataset"] == "indian" and v["indian_prevalent_tb"])
    print("PILOT PACKET BUILT")
    print(f"  folder: {PACKET}")
    print(f"  contents: {sorted(p.name for p in PACKET.iterdir())}")
    print(f"  images copied: {len(list((PACKET / 'images').glob('*')))}")
    print(f"  total reports to grade: {len(items)}  (Indian {n_in} + Western {n_we})")
    print(f"  TB/Indian-prevalent Indian cases: {n_tb}")
    print(f"  rubric: {list(bgp.RUBRIC.keys())} + own_reading")
    print(f"  hidden key: {key_file}")
    print(f"  key inside packet? {(PACKET / key_file.name).exists()}")


if __name__ == "__main__":
    main()
