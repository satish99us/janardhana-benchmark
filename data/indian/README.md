# Indian chest X-ray data

Put your Indian chest X-ray images (.jpg/.jpeg/.png) in this folder, plus a
`manifest.csv` describing them.

## Where to get public Indian chest X-ray data

Some publicly available options to start with (verify the current license and
access terms yourself before use — they change):

- **Indian-origin chest X-ray research datasets** hosted on platforms like
  Kaggle, PhysioNet, and academic repositories. Search for Indian tuberculosis
  and chest X-ray datasets (several Indian TB screening datasets exist with
  labels).
- **Montgomery & Shenzhen TB datasets** — the Shenzhen set is from China, the
  Montgomery set from the US; not Indian, but commonly used. Do NOT label these
  as Indian.
- For a genuinely Indian sample, the strongest path is a small de-identified
  export from your own clinical relationships (e.g. Vijaya) under proper
  consent/IEC — that is also the data your eventual product is built on.

IMPORTANT for the benchmark's credibility: the Indian dataset and the Western
dataset (CheXpert) should be as comparable as possible — same view (frontal),
similar findings present, similar image quality. The cleaner the match, the
more the measured gap reflects population rather than dataset artifacts.

## manifest.csv format

One row per image. Columns:

    filename,pneumonia,pleural_effusion,cardiomegaly,pulmonary_edema,consolidation,atelectasis,pneumothorax,lung_opacity

Values per finding: `1` present, `0` absent, blank or `-1` uncertain/unknown.

Example:

    filename,pneumonia,pleural_effusion,cardiomegaly,pulmonary_edema,consolidation,atelectasis,pneumothorax,lung_opacity
    case001.jpg,1,0,0,0,1,0,0,1
    case002.jpg,0,1,1,0,0,0,0,0
    case003.png,0,0,0,,0,0,0,0

Only the findings present in BOTH your Indian set and CheXpert will produce a
delta; others show as n/a. That's fine for a first run.
