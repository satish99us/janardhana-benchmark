"""
Scoring for the normal-vs-abnormal task.

For each model on each dataset we compute:
  - accuracy           (overall correct rate)
  - sensitivity        (recall on abnormal cases = caught the disease)
  - specificity        (recall on normal cases   = didn't false-alarm)

Then the headline: the DELTA between Western and Indian accuracy for the same
model. Positive delta = worse on Indian data = supports the thesis.

Because sampling is balanced (50/50), accuracy is meaningful and not gameable
by guessing the majority class.
"""


def _norm(label: str) -> str:
    l = (label or "").strip().lower()
    if l.startswith("abn"):
        return "abnormal"
    if l.startswith("nor"):
        return "normal"
    return "invalid"


def score_model_on_dataset(predictions: list, truths: list) -> dict:
    tp = fp = tn = fn = correct = total = invalid = 0
    # "positive" = abnormal (the thing we want to catch)
    for pred, truth in zip(predictions, truths):
        p = _norm(pred.get("assessment", ""))
        t = _norm(truth)
        total += 1
        if p == "invalid":
            invalid += 1
            # an unparseable / hedged answer counts as wrong
            if t == "abnormal":
                fn += 1
            else:
                fp += 1
            continue
        if p == t:
            correct += 1
        if t == "abnormal":
            if p == "abnormal":
                tp += 1
            else:
                fn += 1
        else:  # t == normal
            if p == "normal":
                tn += 1
            else:
                fp += 1
    accuracy = correct / total if total else None
    sensitivity = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    return {
        "n": total,
        "accuracy": accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "invalid_responses": invalid,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def compute_delta(indian: dict, western: dict) -> dict:
    def d(a, b):
        return round(b - a, 4) if (a is not None and b is not None) else None
    return {
        "accuracy_delta": d(indian["accuracy"], western["accuracy"]),
        "sensitivity_delta": d(indian["sensitivity"], western["sensitivity"]),
        "specificity_delta": d(indian["specificity"], western["specificity"]),
    }
