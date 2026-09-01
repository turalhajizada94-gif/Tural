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


def apply_derived(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Build recoded variables, e.g. ESL from 'Is English your first language?'."""
    df = df.copy()
    report: dict[str, dict] = {}
    for name, spec in (config.get("derived") or {}).items():
        source = spec["from"]
        if source not in df.columns:
            report[name] = {"label": spec.get("label", name), "error": f"{source} not in export"}
            continue
        mapping = {int(k): v for k, v in spec["mapping"].items()}
        values = pd.to_numeric(df[source], errors="coerce")
        df[name] = values.map(mapping)
        report[name] = {
            "label": spec.get("label", name),
            "source": source,
            "counts": df[name].value_counts(dropna=False).to_dict(),
            "unmapped": int(values.notna().sum() - df[name].notna().sum()),
        }
    return df, report


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


def build_model_frame(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Assemble the regression design described in config['analysis'].

    Handles the pre-registered specifics: the moderator is mean-centred,
    categorical covariates become dummies against a named reference level, and
    the predictor x moderator interaction is formed after centring.
    """
    spec = config["analysis"]
    outcome = spec["outcome"]
    predictor = spec.get("predictor")
    moderator = spec.get("moderator")
    categorical = set(config.get("demographics", {}).get("categorical") or [])

    data = pd.DataFrame(index=df.index)
    data[outcome] = pd.to_numeric(df[outcome], errors="coerce")
    design: list[str] = []

    if predictor:
        data[predictor] = pd.to_numeric(df[predictor], errors="coerce")
        design.append(predictor)

    moderator_col = None
    if moderator:
        values = pd.to_numeric(df[moderator], errors="coerce")
        if spec.get("centre_moderator"):
            moderator_col = f"{moderator}_c"
            data[moderator_col] = values - values.mean()
        else:
            moderator_col = moderator
            data[moderator_col] = values
        design.append(moderator_col)

    dummy_reference: dict[str, str] = {}
    for cov in spec.get("covariates") or []:
        if cov not in df.columns:
            continue
        if cov in categorical or df[cov].dtype == object:
            dummies = pd.get_dummies(df[cov].astype(str), prefix=cov)
            wanted = f"{cov}_{spec.get('gender_reference')}" if cov == "Gender" else None
            reference = wanted if wanted in dummies.columns else dummies.columns[0]
            dummies = dummies.drop(columns=[reference]).astype(float)
            dummy_reference[cov] = reference.replace(f"{cov}_", "")
            for col in dummies.columns:
                data[col] = dummies[col]
                design.append(col)
        else:
            data[cov] = pd.to_numeric(df[cov], errors="coerce")
            design.append(cov)

    interaction = None
    if predictor and moderator_col:
        interaction = f"{predictor}_x_{moderator}"
        data[interaction] = data[predictor] * data[moderator_col]

    info = {
        "outcome": outcome,
        "predictor": predictor,
        "moderator": moderator,
        "moderator_col": moderator_col,
        "interaction": interaction,
        "design": design,
        "dummy_reference": dummy_reference,
        "continuous": [c for c in (outcome, predictor, moderator_col) if c],
    }
    return data, info


def _em_multivariate_normal(
    values: np.ndarray, max_iter: int = 500, tol: float = 1e-7
) -> tuple[np.ndarray, np.ndarray]:
    """ML estimates of mu and sigma under multivariate normality with missing data."""
    n, p = values.shape
    observed = ~np.isnan(values)
    mu = np.nanmean(values, axis=0)
    sigma = np.ma.cov(np.ma.masked_invalid(values), rowvar=False)
    sigma = np.atleast_2d(np.asarray(sigma.filled(0) if hasattr(sigma, "filled") else sigma))
    sigma = sigma + np.eye(p) * 1e-6

    for _ in range(max_iter):
        sum_x = np.zeros(p)
        sum_xx = np.zeros((p, p))
        for i in range(n):
            obs = observed[i]
            mis = ~obs
            row = values[i].copy()
            correction = np.zeros((p, p))
            if mis.any():
                if obs.any():
                    s_oo = sigma[np.ix_(obs, obs)]
                    s_mo = sigma[np.ix_(mis, obs)]
                    inv = np.linalg.pinv(s_oo)
                    row[mis] = mu[mis] + s_mo @ inv @ (row[obs] - mu[obs])
                    correction[np.ix_(mis, mis)] = sigma[np.ix_(mis, mis)] - s_mo @ inv @ s_mo.T
                else:
                    row = mu.copy()
                    correction = sigma.copy()
            sum_x += row
            sum_xx += np.outer(row, row) + correction

        new_mu = sum_x / n
        new_sigma = sum_xx / n - np.outer(new_mu, new_mu)
        converged = np.max(np.abs(new_mu - mu)) < tol and np.max(np.abs(new_sigma - sigma)) < tol
        mu, sigma = new_mu, new_sigma
        if converged:
            break
    return mu, sigma


def littles_mcar_test(data: pd.DataFrame) -> dict:
    """Little's (1988) test of whether values are missing completely at random.

    The pre-registered plan routes on this: listwise deletion if missingness is
    under 5% and MCAR is not rejected, multiple imputation otherwise.
    """
    from scipy import stats as _stats

    frame = data.apply(pd.to_numeric, errors="coerce")
    if not frame.isna().any().any():
        return {"n_patterns": 1, "statistic": 0.0, "df": 0, "p": None, "no_missing": True}

    values = frame.to_numpy(dtype=float)
    mu, sigma = _em_multivariate_normal(values)

    keys = frame.notna().apply(lambda row: "".join("1" if v else "0" for v in row), axis=1)
    statistic = 0.0
    df_total = 0
    for key, group in frame.groupby(keys):
        obs = np.array([c == "1" for c in key])
        if not obs.any():
            continue
        diff = group.to_numpy(dtype=float)[:, obs].mean(axis=0) - mu[obs]
        inv = np.linalg.pinv(sigma[np.ix_(obs, obs)])
        statistic += len(group) * float(diff @ inv @ diff)
        df_total += int(obs.sum())

    df_total -= frame.shape[1]
    p = float(1 - _stats.chi2.cdf(statistic, df_total)) if df_total > 0 else float("nan")
    return {
        "n_patterns": int(keys.nunique()),
        "statistic": statistic,
        "df": df_total,
        "p": p,
        "no_missing": False,
    }


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
