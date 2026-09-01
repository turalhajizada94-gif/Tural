"""Screen the raw export, score the scales, and write the participant flow.

Reads the most recent file in data/raw/ (or --input), applies every screening rule
in config/study.yaml in a fixed order, and writes:

    data/processed/analysis_sample.csv   cleaned, scored, de-identified cases
    output/participant_flow.csv          one row per exclusion rule
    output/participant_flow.md           the same table plus a prose paragraph
    output/data_cleaning_report.md       reverse scoring, prorating, out-of-range

Usage:
    python scripts/prepare_data.py
    python scripts/prepare_data.py --input data/raw/qualtrics-export-....csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from common import (
    OUTPUT_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    FlowLog,
    all_scale_items,
    coerce_numeric,
    drop_identifying_columns,
    ensure_dirs,
    load_config,
    read_qualtrics_csv,
    score_scales,
)


def newest_raw_file() -> Path:
    candidates = sorted(
        [p for p in RAW_DIR.glob("*.csv")] + [p for p in RAW_DIR.glob("*.tsv")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        sys.exit(
            f"No export found in {RAW_DIR}/.\n"
            "Run scripts/fetch_qualtrics.py, or drop a Qualtrics CSV export in there."
        )
    return candidates[0]


def apply_screening(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, FlowLog]:
    cols = config["columns"]
    rules = config["screening"]
    flow = FlowLog()

    def step(label: str, keep_mask: pd.Series) -> None:
        nonlocal df
        before = len(df)
        df = df[keep_mask.fillna(False)]
        flow.record(label, before, len(df))

    flow.record("Responses recorded in Qualtrics", len(df), len(df))

    channel = cols.get("distribution_channel")
    if rules.get("drop_preview_responses") and channel in df.columns:
        step("Preview / test responses", df[channel].astype(str).str.lower() != "preview")

    consent = rules.get("consent") or {}
    if consent.get("column") in df.columns:
        step("Did not give consent", df[consent["column"]] == consent["required_value"])

    finished = cols.get("finished")
    if rules.get("require_finished") and finished in df.columns:
        step("Did not finish the survey", df[finished].astype(str).isin(["1", "True", "true"]))

    progress = cols.get("progress")
    if rules.get("min_progress") is not None and progress in df.columns:
        step(
            f"Completed less than {rules['min_progress']}% of the survey",
            pd.to_numeric(df[progress], errors="coerce") >= rules["min_progress"],
        )

    for rule in rules.get("eligibility") or []:
        col = rule["column"]
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        mask = pd.Series(True, index=df.index)
        if rule.get("min") is not None:
            mask &= values >= rule["min"]
            step(f"Ineligible on {col} (below {rule['min']})", mask)
            mask = pd.Series(True, index=df.index)
        if rule.get("max") is not None:
            mask &= values <= rule["max"]
            step(f"Ineligible on {col} (above {rule['max']})", mask)

    duration = cols.get("duration")
    if duration in df.columns:
        seconds = pd.to_numeric(df[duration], errors="coerce")
        if rules.get("min_duration_seconds"):
            step(
                f"Implausibly fast (under {rules['min_duration_seconds']} s)",
                seconds >= rules["min_duration_seconds"],
            )
        if rules.get("max_duration_seconds"):
            step(
                f"Implausibly slow (over {rules['max_duration_seconds']} s)",
                seconds <= rules["max_duration_seconds"],
            )

    checks = rules.get("attention_checks") or []
    present = [c for c in checks if c["column"] in df.columns]
    if present:
        failures = sum(
            (pd.to_numeric(df[c["column"]], errors="coerce") != c["correct_value"]).astype(int)
            for c in present
        )
        allowed = rules.get("max_attention_check_failures", 0)
        step(f"Failed more than {allowed} attention check(s)", failures <= allowed)

    return df, flow


def write_reports(flow: FlowLog, scale_report: dict, dropped_cols: list[str], source: Path) -> None:
    flow_df = flow.to_frame()
    flow_df.to_csv(OUTPUT_DIR / "participant_flow.csv", index=False)

    lines = [
        "# Participant flow",
        "",
        f"Source export: `{source.name}`",
        "",
        flow_df.to_markdown(index=False),
        "",
        "## Draft paragraph for the manuscript",
        "",
        flow.to_prose(),
        "",
        "> Check the wording against your ethics protocol before using it, and say "
        "where in the recruitment funnel the initial number came from (invitations "
        "sent, panel approaches, or advertisement reach).",
    ]
    (OUTPUT_DIR / "participant_flow.md").write_text("\n".join(lines) + "\n")

    rows = []
    for name, rep in scale_report.items():
        rows.append(
            {
                "Scale": rep["label"],
                "Variable": name,
                "Items": rep["n_items"],
                "Reverse-scored": rep["n_reversed"],
                "Out-of-range set missing": rep["out_of_range_values_set_missing"],
                "Cases prorated": rep["n_prorated"],
                "Cases left missing": rep["n_scored_missing"],
            }
        )
    report_df = pd.DataFrame(rows)

    missing_note = {
        name: rep["items_missing_from_export"]
        for name, rep in scale_report.items()
        if rep["items_missing_from_export"]
    }

    lines = [
        "# Data cleaning report",
        "",
        f"Source export: `{source.name}`",
        "",
        "## Identifying columns removed on import",
        "",
        (", ".join(f"`{c}`" for c in dropped_cols) if dropped_cols else "None present in export."),
        "",
        "## Scale construction",
        "",
        report_df.to_markdown(index=False),
        "",
    ]
    if missing_note:
        lines += [
            "## Items listed in config but absent from the export",
            "",
            "These need their column names corrected in `config/study.yaml`:",
            "",
        ]
        lines += [f"- **{k}**: {', '.join(v)}" for k, v in missing_note.items()]
        lines.append("")
    (OUTPUT_DIR / "data_cleaning_report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None)
    args = parser.parse_args()

    config = load_config()
    ensure_dirs()

    source = args.input or newest_raw_file()
    print(f"Reading {source}")
    df = read_qualtrics_csv(source)
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    df, dropped_cols = drop_identifying_columns(df, config)
    if dropped_cols:
        print(f"  dropped identifying columns: {', '.join(dropped_cols)}")

    numeric_cols = all_scale_items(config) + config["demographics"]["continuous"]
    numeric_cols += [c["column"] for c in config["screening"].get("attention_checks") or []]
    df = coerce_numeric(df, numeric_cols)

    df, flow = apply_screening(df, config)
    print("\nParticipant flow:")
    print(flow.to_frame().to_string(index=False))

    df, scale_report = score_scales(df, config)

    keep = [config["columns"]["response_id"]]
    keep += config["demographics"]["continuous"] + config["demographics"]["categorical"]
    keep += list(config["scales"].keys())
    keep += all_scale_items(config)
    keep = [c for c in dict.fromkeys(keep) if c in df.columns]

    out_path = PROCESSED_DIR / "analysis_sample.csv"
    df[keep].to_csv(out_path, index=False)

    write_reports(flow, scale_report, dropped_cols, source)

    print(f"\nWrote {out_path} (N = {len(df)})")
    print(f"Wrote {OUTPUT_DIR / 'participant_flow.md'}")
    print(f"Wrote {OUTPUT_DIR / 'data_cleaning_report.md'}")
    print("\nNext: python scripts/analyse.py")


if __name__ == "__main__":
    main()
