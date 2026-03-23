"""
Stribeck Optics — Camera-based bloom radius measurement.

Captures frames from a Raspberry Pi Camera Module (or USB webcam) while the
oscillator driver runs, and computes the bloom (starburst) radius of the
LED point source.  Outputs a CSV of:

    timestamp, duty_pct, bloom_radius_px, peak_intensity, snr

for downstream patent comparison between the control (steady LED) and the
modulated oscillator.

Usage:
    # Control run — steady LED:
    python measure_bloom.py --label control --duration 10

    # Modulated run — with oscillator envelope:
    python measure_bloom.py --label modulated --duration 10

    # Offline analysis of saved frames:
    python measure_bloom.py --analyze results/

Hardware:
    Raspberry Pi Camera Module v2 (or any V4L2 camera).
    LED mounted 2 m from camera, aimed at a white diffuser board.

N. Joven, 2026.  CC0.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


# ---------------------------------------------------------------------------
# Bloom analysis
# ---------------------------------------------------------------------------


def compute_bloom_radius(
    frame_gray: "np.ndarray", threshold_ratio: float = 0.1
) -> dict:
    """
    Measure the bloom radius of a bright point source in a grayscale frame.

    Algorithm:
        1. Find the peak pixel (centroid of the light source).
        2. Threshold at `threshold_ratio * peak` to get the "bloom" region.
        3. Compute the equivalent circular radius of that region.
        4. Return peak intensity, bloom radius, and signal-to-noise ratio.
    """
    peak_val = float(frame_gray.max())
    if peak_val < 10:
        return {"peak": peak_val, "bloom_radius_px": 0.0, "snr": 0.0}

    # Centroid of saturated region
    thresh = threshold_ratio * peak_val
    mask = frame_gray >= thresh
    bloom_area_px = int(mask.sum())
    bloom_radius = (bloom_area_px / 3.14159) ** 0.5

    # SNR: peak over background std
    bg = frame_gray[~mask]
    bg_std = float(bg.std()) if bg.size > 0 else 1.0
    snr = peak_val / max(bg_std, 1e-6)

    return {
        "peak": peak_val,
        "bloom_radius_px": round(bloom_radius, 2),
        "snr": round(snr, 2),
    }


# ---------------------------------------------------------------------------
# Capture loop
# ---------------------------------------------------------------------------


def capture_loop(
    label: str,
    duration_s: float = 10.0,
    output_dir: str = "results",
    camera_index: int = 0,
    save_frames: bool = False,
) -> str:
    """Capture frames, measure bloom, write CSV.  Returns path to CSV."""
    if not _HAS_CV2 or not _HAS_NUMPY:
        print(
            "ERROR: numpy and opencv-python are required. "
            "Install with:  pip install numpy opencv-python",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, f"bloom_{label}.csv")
    frame_dir = os.path.join(output_dir, f"frames_{label}")
    if save_frames:
        os.makedirs(frame_dir, exist_ok=True)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {camera_index}.", file=sys.stderr)
        sys.exit(1)

    # Lock exposure so brightness changes come only from the oscillator
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # manual mode
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # low exposure to avoid saturation

    print(f"Recording '{label}' for {duration_s:.0f}s → {csv_path}")
    t0 = time.monotonic()
    rows = []

    try:
        while (time.monotonic() - t0) < duration_s:
            ret, frame = cap.read()
            if not ret:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            t_elapsed = round(time.monotonic() - t0, 3)
            result = compute_bloom_radius(gray)
            row = {"time_s": t_elapsed, "label": label, **result}
            rows.append(row)

            if save_frames:
                fname = os.path.join(frame_dir, f"frame_{t_elapsed:08.3f}.png")
                cv2.imwrite(fname, gray)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()

    # Write CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} samples to {csv_path}")
    else:
        print("No frames captured.")

    return csv_path


# ---------------------------------------------------------------------------
# Offline comparison analysis
# ---------------------------------------------------------------------------


def compare_runs(results_dir: str) -> None:
    """Load control + modulated CSVs and print summary comparison."""
    if not _HAS_NUMPY:
        print("ERROR: numpy required for analysis.", file=sys.stderr)
        sys.exit(1)

    control_path = os.path.join(results_dir, "bloom_control.csv")
    mod_path = os.path.join(results_dir, "bloom_modulated.csv")

    for p in (control_path, mod_path):
        if not os.path.exists(p):
            print(f"Missing: {p}", file=sys.stderr)
            sys.exit(1)

    def load(path):
        with open(path) as f:
            reader = csv.DictReader(f)
            return [
                {
                    "bloom": float(r["bloom_radius_px"]),
                    "peak": float(r["peak"]),
                    "snr": float(r["snr"]),
                }
                for r in reader
            ]

    ctrl = load(control_path)
    mod = load(mod_path)

    def stats(data, key):
        vals = np.array([d[key] for d in data])
        return {"mean": float(vals.mean()), "std": float(vals.std())}

    print("\n=== Bloom Radius Comparison ===\n")
    print(f"  {'Metric':<25} {'Control':>12} {'Modulated':>12} {'Reduction':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12}")
    for key, unit in [
        ("bloom", "px"),
        ("peak", ""),
        ("snr", ""),
    ]:
        c = stats(ctrl, key)
        m = stats(mod, key)
        if c["mean"] > 0:
            reduction = (c["mean"] - m["mean"]) / c["mean"] * 100
        else:
            reduction = 0
        print(
            f"  {key + ' (' + unit + ')':<25} "
            f"{c['mean']:>9.2f}±{c['std']:<2.1f} "
            f"{m['mean']:>9.2f}±{m['std']:<2.1f} "
            f"{reduction:>+10.1f}%"
        )

    print(
        "\nA negative bloom reduction means the modulated signal produces a "
        "SMALLER starburst — this is the patent claim."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stribeck Optics — camera-based bloom measurement."
    )
    sub = parser.add_subparsers(dest="command")

    cap = sub.add_parser("capture", help="Capture frames and measure bloom.")
    cap.add_argument("--label", required=True, help="Run label (e.g. 'control').")
    cap.add_argument(
        "--duration", type=float, default=10.0, help="Capture duration in seconds."
    )
    cap.add_argument("--output", default="results", help="Output directory.")
    cap.add_argument("--camera", type=int, default=0, help="Camera index.")
    cap.add_argument(
        "--save-frames", action="store_true", help="Save individual frames as PNGs."
    )

    cmp = sub.add_parser("compare", help="Compare control vs modulated runs.")
    cmp.add_argument("results_dir", help="Directory containing bloom CSVs.")

    args = parser.parse_args()

    if args.command == "capture":
        capture_loop(
            label=args.label,
            duration_s=args.duration,
            output_dir=args.output,
            camera_index=args.camera,
            save_frames=args.save_frames,
        )
    elif args.command == "compare":
        compare_runs(args.results_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
