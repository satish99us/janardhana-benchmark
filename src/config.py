"""
Central configuration for the Janardhana benchmark.

Everything that you might want to tweak lives here so you don't have to
hunt through the code: which findings we score, which model versions we
call, where data lives, and how many cases to run.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_INDIAN = ROOT / "data" / "indian"
DATA_CHEXPERT = ROOT / "data" / "chexpert"
RESULTS = ROOT / "results"
PROMPTS = ROOT / "prompts"

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------
# PRIMARY TASK: normal vs abnormal.
# This is the only apples-to-apples task our two real datasets both support:
#   - IN-CXR (NIRT, India): labeled normal / abnormal only
#   - CheXpert (Stanford, West): per-finding, but we collapse to normal/abnormal
#     (any positive finding => abnormal) so the two line up exactly.
#
# This is also the stronger headline: "frontier AI is X% worse at even telling
# normal from abnormal on Indian chest X-rays."
#
# The optional per-finding scoring (for richer future data like a Vijaya export)
# is kept available but is NOT the default — IN-CXR has no per-finding labels.
TASK_LABELS = ["normal", "abnormal"]

# Kept for the future per-finding mode only (richly-labeled data later):
FINDINGS = [
    "pneumonia",
    "pleural_effusion",
    "cardiomegaly",
    "pulmonary_edema",
    "consolidation",
    "atelectasis",
    "pneumothorax",
    "lung_opacity",
]

# ---------------------------------------------------------------------------
# Balanced sampling — CRITICAL
# ---------------------------------------------------------------------------
# IN-CXR is ~93% normal (102,122 normal vs 8,232 abnormal). CheXpert is also
# imbalanced. If we sampled naively, models could score high just by guessing
# "normal" and the comparison would be meaningless. So we force a balanced
# sample: equal normal and abnormal from EACH dataset.
#
# CASES_PER_CLASS = number of EACH class (normal/abnormal) sampled per dataset.
# 120 images total, run across each model. Scale up after first signal.
CASES_PER_CLASS = 30  # pilot: 30 Indian + 30 Western

# ---------------------------------------------------------------------------
# Models under test
# ---------------------------------------------------------------------------
# IMPORTANT: pin exact versions. Reproducibility and citability depend on it.
# Update these strings to the current model IDs when you run. The run date is
# stamped automatically into results so your eventual writeup can say exactly
# what was tested and when.
#
# Set "enabled": False for any model whose key you don't have yet — the
# harness will simply skip it and run whatever is available.
MODELS = {
    "claude": {
        "enabled": True,
        "provider": "anthropic",
        # Use the strongest available vision model. Update to current ID.
        "model_id": "claude-opus-4-8",
        "label": "Claude (Anthropic)",
    },
    "gpt": {
        "enabled": True,
        "provider": "openai",
        "model_id": "gpt-5.5-2026-04-23",  # verified available 2026-06-14
        "label": "GPT-5.5 (OpenAI)",
    },
    "gemini": {
        "enabled": True,
        "provider": "google",
        "model_id": "gemini-3.1-pro-preview",  # verified available 2026-06-14
        "label": "Gemini 3.1 Pro (Google)",
    },
    # Placeholder for later — specialized radiology model.
    # Harrison.rad.1 has no public API as of now; leave disabled and add a
    # manual-sample column later, or wire a research API here if granted.
    "harrison": {
        "enabled": False,
        "provider": "manual",
        "model_id": "harrison-rad-1.5",
        "label": "Harrison.Rad.1.5 (specialized)",
    },
}

# ---------------------------------------------------------------------------
# Run controls
# ---------------------------------------------------------------------------
# How many times to retry a failed API call before giving up on a case.
MAX_RETRIES = 3

# Seconds to wait between retries (exponential backoff base).
RETRY_BACKOFF = 2.0


# ---------------------------------------------------------------------------
# Grading rubric (option B: blinded radiologist grading of generated reports)
# ---------------------------------------------------------------------------
# The radiologist grades each report (blind to model and to dataset) on these
# axes. Designed so the result quantifies WHERE models fail, not just whether.
RUBRIC = {
    "main_finding_caught": {
        "question": "Did the report correctly identify the main finding(s) visible on this X-ray?",
        "options": ["yes", "partial", "no"],
    },
    "dangerous_miss": {
        "question": "Did the report MISS any clinically important finding that is actually present? (false negative)",
        "options": ["no", "yes"],
    },
    "hallucination": {
        "question": "Did the report describe a finding that is NOT actually present? (false positive / hallucination)",
        "options": ["no", "yes"],
    },
    "overall_soundness": {
        "question": "Overall, how clinically sound is this report? (1 = unusable, 5 = excellent)",
        "options": ["1", "2", "3", "4", "5"],
    },
}
