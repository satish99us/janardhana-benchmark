"""
STEP 3 of option B: score the radiologist's blinded grades.

Joins the radiologist's grades.json (keyed by blind CASE id) with the hidden
key (which reveals dataset + model for each blind id), and computes the
Indian-vs-Western quality gap per rubric axis — the headline result.

USAGE:  python -m src.score_grades grades.json _key_<stamp>.json
"""

import sys
import json
import datetime
from pathlib import Path
from .config import RESULTS, RUBRIC


def _load(arg):
    p = RESULTS / arg
    if not p.exists():
        p = Path(arg)
    return json.loads(p.read_text())


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m src.score_grades grades.json _key_<stamp>.json")
        sys.exit(1)
    grades = _load(sys.argv[1])
    key = _load(sys.argv[2])

    # bucket grades by dataset (and by model, for a secondary view)
    by_dataset = {"indian": [], "western": []}
    by_model = {}
    for blind_id, g in grades.items():
        meta = key.get(blind_id)
        if not meta:
            continue
        by_dataset[meta["dataset"]].append(g)
        by_model.setdefault(meta["model_label"], {"indian": [], "western": []})
        by_model[meta["model_label"]][meta["dataset"]].append(g)

    report = {
        "scored": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_graded": len(grades),
        "n_indian": len(by_dataset["indian"]),
        "n_western": len(by_dataset["western"]),
        "overall": _gap(by_dataset["indian"], by_dataset["western"]),
        "by_model": {m: _gap(d["indian"], d["western"]) for m, d in by_model.items()},
    }

    out = RESULTS / "grading_result.json"
    out.write_text(json.dumps(report, indent=2))
    print(_format(report))
    print(f"\nFull result: {out}")
    print("Paste this back to Claude for interpretation.")


def _gap(indian_grades, western_grades):
    """Compute per-axis metrics for each population and the India-vs-West gap."""
    def agg(grades_list):
        n = len(grades_list)
        if n == 0:
            return None
        out = {}
        # main_finding_caught: fraction "yes"
        out["main_finding_caught_yes"] = sum(1 for g in grades_list if g.get("main_finding_caught") == "yes") / n
        # dangerous_miss: fraction "yes" (BAD — lower is better)
        out["dangerous_miss_rate"] = sum(1 for g in grades_list if g.get("dangerous_miss") == "yes") / n
        # hallucination: fraction "yes" (BAD — lower is better)
        out["hallucination_rate"] = sum(1 for g in grades_list if g.get("hallucination") == "yes") / n
        # overall_soundness: mean of 1-5
        vals = [int(g["overall_soundness"]) for g in grades_list if str(g.get("overall_soundness", "")).isdigit()]
        out["overall_soundness_mean"] = (sum(vals) / len(vals)) if vals else None
        out["n"] = n
        return out

    ind, west = agg(indian_grades), agg(western_grades)
    gap = None
    if ind and west:
        gap = {
            # for "good" metrics, gap = west - india (positive = worse on Indian)
            "main_finding_caught_gap": round(west["main_finding_caught_yes"] - ind["main_finding_caught_yes"], 4),
            "soundness_gap": (round(west["overall_soundness_mean"] - ind["overall_soundness_mean"], 4)
                              if west["overall_soundness_mean"] and ind["overall_soundness_mean"] else None),
            # for "bad" metrics, gap = india - west (positive = worse on Indian)
            "dangerous_miss_gap": round(ind["dangerous_miss_rate"] - west["dangerous_miss_rate"], 4),
            "hallucination_gap": round(ind["hallucination_rate"] - west["hallucination_rate"], 4),
        }
    return {"indian": ind, "western": west, "gap_positive_means_worse_on_indian": gap}


def _format(r):
    L = ["", "=" * 64, "BLINDED RADIOLOGIST GRADING RESULT", "=" * 64]
    L.append(f"Graded: {r['n_graded']}   Indian: {r['n_indian']}   Western: {r['n_western']}")
    o = r["overall"]
    if o and o["gap_positive_means_worse_on_indian"]:
        g = o["gap_positive_means_worse_on_indian"]
        i, w = o["indian"], o["western"]
        L.append("")
        L.append("OVERALL (positive gap = worse on Indian X-rays)")
        L.append("-" * 64)
        L.append(f"  main finding caught:  India {i['main_finding_caught_yes']:.2f}  "
                 f"West {w['main_finding_caught_yes']:.2f}  gap {g['main_finding_caught_gap']:+.3f}")
        L.append(f"  dangerous misses:     India {i['dangerous_miss_rate']:.2f}  "
                 f"West {w['dangerous_miss_rate']:.2f}  gap {g['dangerous_miss_gap']:+.3f}")
        L.append(f"  hallucinations:       India {i['hallucination_rate']:.2f}  "
                 f"West {w['hallucination_rate']:.2f}  gap {g['hallucination_gap']:+.3f}")
        if g["soundness_gap"] is not None:
            L.append(f"  soundness (1-5):      India {i['overall_soundness_mean']:.2f}  "
                     f"West {w['overall_soundness_mean']:.2f}  gap {g['soundness_gap']:+.3f}")
    L.append("")
    L.append("Positive 'main finding' / 'soundness' gaps and positive 'dangerous miss' /")
    L.append("'hallucination' gaps all mean models did WORSE on Indian X-rays.")
    return "\n".join(L)


if __name__ == "__main__":
    main()
