"""
Convert DICOM chest X-rays to PNG (for IN-CXR, which ships as DICOM).

The model APIs need standard images (PNG/JPG), not raw DICOM. This also applies
proper windowing so the PNG looks like the radiograph a radiologist sees, rather
than a washed-out raw array — important so image quality doesn't add noise to
the comparison.

USAGE:
    python -m src.convert_dicom /path/to/dicom/folder /path/to/output/png/folder

Converts every .dcm (and extensionless DICOM) found under the input folder.
Handles MONOCHROME1/2, rescale slope/intercept, and VOI LUT / window settings.
"""

import sys
import argparse
from pathlib import Path

import numpy as np


def _to_8bit(arr: np.ndarray, ds) -> np.ndarray:
    arr = arr.astype(np.float32)

    # Rescale (slope/intercept) if present
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr * slope + intercept

    # Windowing: use WindowCenter/Width if present, else min-max
    wc = getattr(ds, "WindowCenter", None)
    ww = getattr(ds, "WindowWidth", None)
    if wc is not None and ww is not None:
        # these can be lists (MultiValue)
        if isinstance(wc, (list, tuple)) or hasattr(wc, "__iter__") and not isinstance(wc, (int, float)):
            wc = float(wc[0])
        else:
            wc = float(wc)
        if isinstance(ww, (list, tuple)) or hasattr(ww, "__iter__") and not isinstance(ww, (int, float)):
            ww = float(ww[0])
        else:
            ww = float(ww)
        lo, hi = wc - ww / 2.0, wc + ww / 2.0
    else:
        lo, hi = float(arr.min()), float(arr.max())

    if hi <= lo:
        hi = lo + 1.0
    arr = np.clip((arr - lo) / (hi - lo), 0, 1) * 255.0
    arr = arr.astype(np.uint8)

    # MONOCHROME1 means high value = dark; invert so bones are bright as usual
    if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        arr = 255 - arr
    return arr


def convert_one(dcm_path: Path, out_path: Path) -> bool:
    import pydicom
    from PIL import Image
    try:
        ds = pydicom.dcmread(str(dcm_path))
        pixels = ds.pixel_array
        img8 = _to_8bit(pixels, ds)
        Image.fromarray(img8).convert("L").save(out_path)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ! failed {dcm_path.name}: {e}")
        return False


def _is_dicom(p: Path) -> bool:
    if p.suffix.lower() in (".dcm", ".dicom"):
        return True
    # extensionless DICOMs: peek for the DICM magic at offset 128
    if p.suffix == "" and p.is_file():
        try:
            with open(p, "rb") as f:
                f.seek(128)
                return f.read(4) == b"DICM"
        except Exception:
            return False
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="folder containing DICOM files")
    ap.add_argument("output", help="folder to write PNGs into")
    args = ap.parse_args()

    in_dir, out_dir = Path(args.input), Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    dicoms = [p for p in in_dir.rglob("*") if _is_dicom(p)]
    if not dicoms:
        print(f"No DICOM files found under {in_dir}")
        sys.exit(1)

    print(f"Converting {len(dicoms)} DICOM files -> PNG ...")
    ok = 0
    for i, dcm in enumerate(dicoms):
        out_path = out_dir / f"{dcm.stem or 'img'}_{i:05d}.png"
        if convert_one(dcm, out_path):
            ok += 1
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(dicoms)} done")
    print(f"Done: {ok}/{len(dicoms)} converted into {out_dir}")


if __name__ == "__main__":
    main()
