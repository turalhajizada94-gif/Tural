"""Shared helpers: config loading, Qualtrics CSV parsing, scale scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "study.yaml"
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUT_DIR = REPO_ROOT / "output"


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def read_qualtrics_csv(path: Path | str) -> pd.DataFrame:
    """Read a Qualtrics CSV export.

    Qualtrics writes three header rows: machine column names, the full question
    text, and a JSON ImportId block. Only the first is wanted as the header, so
    the other two are dropped. Files already stripped of them are handled too.
    """
    header = pd.read_csv(path, nrows=0).columns.tolist()
    skip = []
    probe = pd.read_csv(path, skiprows=[0], nrows=2, header=None, dtype=str)
    if not probe.empty and probe.iloc[0].astype(str).str.contains("ImportId").any():
        skip = [1]
    elif len(probe) > 1 and probe.iloc[1].astype(str).str.contains("ImportId").any():
        skip = [1, 2]

    df = pd.read_csv(path, skiprows=skip, low_memory=False)
    df.columns = header
    return df


def drop_identifying_columns(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[str]]:
    to_drop = [c for c in config["columns"].get("drop_on_import", []) if c in df.columns]
    return df.drop(columns=to_drop), to_drop


def coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def all_scale_items(config: dict) -> list[str]:
    items: list[str] = []
    for spec in config["scales"].values():
        items.extend(spec["items"])
    return items


def reverse_score(series: pd.Series, response_range: list[int]) -> pd.Series:
    low, high = response_range
    return (low + high) - series


def score_scales(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Reverse-score flagged items and compute one composite per scale.

    Returns the augmented frame and a per-scale report of how many items were
    reversed, how many cases were prorated, and how many were left missing.
    """
    df = df.copy()
    max_missing = config["screening"]["max_missing_proportion_per_scale"]
    report: dict[str, dict] = {}

    for name, spec in config["scales"].items():
        items = [i for i in spec["items"] if i in df.columns]
        missing_items = [i for i in spec["items"] if i not in df.columns]
        low, high = spec["response_range"]

        out_of_range = 0
        for item in items:
            invalid = df[item].notna() & ((df[item] < low) | (df[item] > high))
            out_of_range += int(invalid.sum())
            df.loc[invalid, item] = np.nan

        scored_cols = []
        for item in items:
            if item in spec.get("reverse_items") or []:
                col = f"{item}_r"
                df[col] = reverse_score(df[item], spec["response_range"])
                scored_cols.append(col)
            else:
                scored_cols.append(item)

        block = df[scored_cols]
        missing_prop = block.isna().mean(axis=1)
        eligible = missing_prop <= max_missing

        agg = block.mean(axis=1) if spec["score"] == "mean" else block.sum(axis=1)
        df[name] = agg.where(eligible)

        report[name] = {
            "label": spec["label"],
            "n_items": len(items),
            "items_missing_from_export": missing_items,
            "n_reversed": len(spec.get("reverse_items") or []),
            "out_of_range_values_set_missing": out_of_range,
            "n_prorated": int(((missing_prop > 0) & eligible).sum()),
            "n_scored_missing": int((~eligible).sum()),
        }

    return df, report


def cronbach_alpha(items: pd.DataFrame) -> float:
    """Cronbach's alpha on complete cases."""
    data = items.dropna()
    k = data.shape[1]
    if k < 2 or len(data) < 3:
        return float("nan")
    item_var = data.var(axis=0, ddof=1).sum()
    total_var = data.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return (k / (k - 1)) * (1 - item_var / total_var)


@dataclass
class FlowLog:
    """Accumulates the participant flow, one line per exclusion rule."""

    steps: list[dict] = field(default_factory=list)

    def record(self, label: str, before: int, after: int) -> None:
        self.steps.append(
            {"step": label, "n_before": before, "n_excluded": before - after, "n_after": after}
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps)

    def to_prose(self) -> str:
        if not self.steps:
            return ""
        start = self.steps[0]["n_before"]
        final = self.steps[-1]["n_after"]
        removed = [s for s in self.steps if s["n_excluded"] > 0]
        clauses = [f"{s['n_excluded']} {s['step'].lower()}" for s in removed]
        if clauses:
            body = "; ".join(clauses)
            return (
                f"Of the {start} responses recorded in Qualtrics, {start - final} were "
                f"excluded ({body}), leaving a final analysed sample of N = {final}."
            )
        return f"All {start} recorded responses were retained (N = {final})."


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
