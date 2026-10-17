# Western baseline — CheXpert

Put Western chest X-ray images here plus a `manifest.csv` in the same format
as the Indian folder.

## Recommended source: CheXpert (Stanford)

CheXpert is a large, public, labeled chest X-ray dataset from Stanford — the
standard Western benchmark. Request access via the Stanford ML Group site and
follow their data use agreement. MIMIC-CXR (MIT/PhysioNet) is an equally valid
alternative and also requires credentialed access.

Why these: they are widely cited and trusted, so reviewers and the labs you
pitch will accept them as a legitimate Western baseline. Using a trusted public
baseline is what lets you claim the India-vs-West delta credibly.

## Matching matters

Pick a CheXpert subset that's comparable to your Indian sample:
- frontal view only
- similar mix of findings (don't compare all-normal Western against
  all-abnormal Indian — that would confound the result)
- similar number of cases

The harness scores both with the identical model + identical prompt, so the
only thing that should differ is the patient population. Keep everything else
as matched as you can.

## manifest.csv format

Identical to the Indian folder:

    filename,pneumonia,pleural_effusion,cardiomegaly,pulmonary_edema,consolidation,atelectasis,pneumothorax,lung_opacity

`1` present, `0` absent, blank/`-1` uncertain. CheXpert ships with labels you
can map directly into these columns (CheXpert uses 1.0 / 0.0 / -1.0 / blank,
which maps cleanly: 1->1, 0->0, -1 or blank -> uncertain).
