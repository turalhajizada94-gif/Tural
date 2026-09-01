"""Generate a fake Qualtrics-style export so the pipeline can be tested safely.

This exists purely so you can run the whole workflow end to end before your real
data is in hand, and so the scripts can be verified without touching participant
records. The output mimics a real export: three header rows, Qualtrics metadata
columns, preview responses, incompletes, speeders, attention-check failures,
ineligible ages and scattered missing items.

Usage:
    python scripts/make_synthetic_data.py --n-final 180
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import RAW_DIR, ensure_dirs, load_config

RNG = np.random.default_rng(4414)

META = [
    "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
    "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
    "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
    "DistributionChannel", "UserLanguage",
]


def likert(latent: np.ndarray, low: int, high: int, noise: float) -> np.ndarray:
    values = latent + RNG.normal(0, noise, size=latent.shape)
    scaled = (values - values.min()) / (values.max() - values.min())
    return np.clip(np.round(scaled * (high - low) + low), low, high).astype(float)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-final", type=int, default=180, help="target clean sample size")
    args = parser.parse_args()

    config = load_config()
    ensure_dirs()

    n_final = args.n_final
    n_preview, n_noconsent, n_incomplete = 3, 6, 14
    n_speeder, n_failcheck, n_underage = 7, 5, 4
    n_total = n_final + n_preview + n_noconsent + n_incomplete + n_speeder + n_failcheck + n_underage

    # Correlated latent traits so the example model has something to find.
    stress_latent = RNG.normal(0, 1, n_total)
    coping_latent = -0.45 * stress_latent + RNG.normal(0, 0.9, n_total)
    wellbeing_latent = -0.35 * stress_latent + 0.50 * coping_latent + RNG.normal(0, 0.8, n_total)
    latents = {"stress": stress_latent, "coping": coping_latent, "wellbeing": wellbeing_latent}

    df = pd.DataFrame(
        {
            "StartDate": pd.date_range("2026-07-01", periods=n_total, freq="3h").astype(str),
            "EndDate": pd.date_range("2026-07-01 00:20", periods=n_total, freq="3h").astype(str),
            "Status": 0,
            "IPAddress": [f"203.0.113.{i % 254 + 1}" for i in range(n_total)],
            "Progress": 100,
            "Duration (in seconds)": RNG.integers(400, 1500, n_total),
            "Finished": 1,
            "RecordedDate": pd.date_range("2026-07-01 00:21", periods=n_total, freq="3h").astype(str),
            "ResponseId": [f"R_{RNG.integers(10**14, 10**15)}" for _ in range(n_total)],
            "RecipientLastName": "",
            "RecipientFirstName": "",
            "RecipientEmail": "",
            "ExternalReference": "",
            "LocationLatitude": RNG.normal(-37.8, 0.2, n_total).round(4),
            "LocationLongitude": RNG.normal(144.9, 0.2, n_total).round(4),
            "DistributionChannel": "anonymous",
            "UserLanguage": "EN",
            "Consent": 1,
            "Age": RNG.integers(18, 66, n_total),
            "Gender": RNG.choice(["Woman", "Man", "Non-binary", "Prefer not to say"],
                                 n_total, p=[0.62, 0.32, 0.04, 0.02]),
            "Education": RNG.choice(["Secondary", "Undergraduate", "Postgraduate"],
                                    n_total, p=[0.25, 0.5, 0.25]),
            "AC1": 4,
        }
    )

    for name, spec in config["scales"].items():
        low, high = spec["response_range"]
        for item in spec["items"]:
            values = likert(latents[name], low, high, noise=0.75)
            if item in (spec.get("reverse_items") or []):
                values = (low + high) - values
            df[item] = values

    # Sprinkle item-level missingness.
    item_cols = [c for spec in config["scales"].values() for c in spec["items"]]
    for col in item_cols:
        idx = RNG.choice(n_total, size=RNG.integers(0, 4), replace=False)
        df.loc[idx, col] = np.nan

    cursor = n_final
    def take(n: int) -> np.ndarray:
        nonlocal cursor
        idx = np.arange(cursor, cursor + n)
        cursor += n
        return idx

    df.loc[take(n_preview), "DistributionChannel"] = "preview"
    df.loc[take(n_noconsent), "Consent"] = 0
    incomplete = take(n_incomplete)
    df.loc[incomplete, "Finished"] = 0
    df.loc[incomplete, "Progress"] = RNG.integers(15, 95, n_incomplete)
    df.loc[take(n_speeder), "Duration (in seconds)"] = RNG.integers(45, 175, n_speeder)
    df.loc[take(n_failcheck), "AC1"] = RNG.choice([1, 2, 3, 5], n_failcheck)
    df.loc[take(n_underage), "Age"] = RNG.integers(14, 18, n_underage)

    df = df.sample(frac=1, random_state=11).reset_index(drop=True)

    question_text = {c: f"Question text for {c}" for c in df.columns}
    import_ids = {c: json.dumps({"ImportId": c}) for c in df.columns}
    header_rows = pd.DataFrame([question_text, import_ids])[df.columns]

    out = RAW_DIR / "synthetic-qualtrics-export.csv"
    pd.concat([header_rows, df], ignore_index=True).to_csv(out, index=False)

    print(f"Wrote {out}")
    print(f"  {n_total} raw rows -> {n_final} expected after screening")
    print("  This is fake data. Delete it before analysing your real export.")


if __name__ == "__main__":
    main()
