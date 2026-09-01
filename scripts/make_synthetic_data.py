"""Generate a fake Qualtrics-style export so the pipeline can be tested safely.

This exists so the workflow can be verified without touching participant
records. The output mimics a real export of this study: three header rows,
Qualtrics metadata, an ESL question, NAQ-R and Mini-IPIP6 Openness items, two
attention checks, plus preview responses, incompletes, speeders, under-25s and
scattered missing items.

The simulated data contains a real ESL main effect and a real ESL x Openness
interaction, so the hypothesis tests have something to detect. None of it means
anything about the actual study.

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
    n_speeder, n_notcitizen, n_ineligible_age = 7, 5, 4
    n_total = (
        n_final + n_preview + n_noconsent + n_incomplete
        + n_speeder + n_notcitizen + n_ineligible_age
    )

    # Q5: 1 = English is my first language; 2-5 = it is not, at decreasing fluency.
    proficiency = RNG.choice([1, 2, 3, 4, 5], n_total, p=[0.58, 0.12, 0.18, 0.09, 0.03])
    esl = (proficiency > 1).astype(float)

    openness_latent = RNG.normal(0, 1, n_total)
    # Main effect of ESL, plus an interaction: the ESL penalty shrinks as
    # Openness rises, which is the hypothesised shielding effect.
    bullying_latent = (
        0.55 * esl
        - 0.30 * openness_latent
        - 0.35 * esl * openness_latent
        + RNG.normal(0, 0.85, n_total)
    )

    df = pd.DataFrame(
        {
            "StartDate": pd.date_range("2026-07-01", periods=n_total, freq="3h").astype(str),
            "EndDate": pd.date_range("2026-07-01 00:20", periods=n_total, freq="3h").astype(str),
            "Status": 0,
            "IPAddress": [f"203.0.113.{i % 254 + 1}" for i in range(n_total)],
            "Progress": 100,
            "Duration (in seconds)": RNG.integers(600, 1500, n_total),
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
            "QID127848236": 1,                              # consent, 1 = Agree
            "QID127848235": 1,                              # Australian citizen/PR
            "QID127848233": 1,                              # aged 25-65
            "QID127848234": 1,                              # fluent in English
            "Q1": RNG.integers(1, 42, n_total),             # age code; 1 = 25 years
            "Q2": RNG.choice([1, 2, 3], n_total, p=[0.68, 0.24, 0.08]),  # employment
            "Q3": RNG.choice([1, 2, 3, 4], n_total, p=[0.52, 0.42, 0.04, 0.02]),  # gender
            "Q5": proficiency,
            "Q6": RNG.integers(1, 20, n_total),             # industry
            "Q_DataPolicyViolations": "",
        }
    )

    latents = {"bullying": bullying_latent, "openness": openness_latent}
    for name, spec in config["scales"].items():
        low, high = spec["response_range"]
        for item in spec["items"]:
            values = likert(latents[name], low, high, noise=0.8)
            if item in (spec.get("reverse_items") or []):
                values = (low + high) - values
            df[item] = values

    item_cols = [c for spec in config["scales"].values() for c in spec["items"]]
    for col in item_cols:
        idx = RNG.choice(n_total, size=RNG.integers(0, 3), replace=False)
        df.loc[idx, col] = np.nan

    cursor = n_final

    def take(n: int) -> np.ndarray:
        nonlocal cursor
        idx = np.arange(cursor, cursor + n)
        cursor += n
        return idx

    df.loc[take(n_preview), "DistributionChannel"] = "preview"
    df.loc[take(n_noconsent), "QID127848236"] = 2
    incomplete = take(n_incomplete)
    df.loc[incomplete, "Finished"] = 0
    df.loc[incomplete, "Progress"] = RNG.integers(15, 95, n_incomplete)
    df.loc[take(n_speeder), "Duration (in seconds)"] = RNG.integers(45, 175, n_speeder)
    df.loc[take(n_notcitizen), "QID127848235"] = 2
    df.loc[take(n_ineligible_age), "QID127848233"] = 2

    df = df.sample(frac=1, random_state=11).reset_index(drop=True)

    question_text = {c: f"Question text for {c}" for c in df.columns}
    import_ids = {c: json.dumps({"ImportId": c}) for c in df.columns}
    header_rows = pd.DataFrame([question_text, import_ids])[df.columns]

    out = RAW_DIR / "synthetic-qualtrics-export.csv"
    pd.concat([header_rows, df], ignore_index=True).to_csv(out, index=False)

    print(f"Wrote {out}")
    print(f"  {n_total} raw rows -> {n_final} expected after screening")
    print("  This is FAKE data. Delete it before analysing your real export.")


if __name__ == "__main__":
    main()
