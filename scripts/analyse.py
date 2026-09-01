"""Produce the descriptive, reliability and assumption-testing outputs.

Reads data/processed/analysis_sample.csv and writes to output/:

    descriptives.md         sample description, scale descriptives, reliabilities
    correlations.csv/.md    intercorrelation matrix with significance stars
    assumptions.md          every assumption test for the model in study.yaml
    fig_histograms.png      distribution of each composite
    fig_residuals.png       residuals vs fitted, and a normal Q-Q plot
    fig_scatter_matrix.png  linearity check across model variables

Usage:
    python scripts/analyse.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

from common import OUTPUT_DIR, PROCESSED_DIR, cronbach_alpha, ensure_dirs, load_config

Z_OUTLIER = 3.29


def stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def describe_sample(df: pd.DataFrame, config: dict) -> list[str]:
    lines = ["## Sample description", "", f"Final analysed sample: **N = {len(df)}**", ""]

    for col in config["demographics"]["continuous"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if values.empty:
                continue
            lines.append(
                f"- **{col}**: M = {values.mean():.2f}, SD = {values.std(ddof=1):.2f}, "
                f"range {values.min():.0f}–{values.max():.0f} (n = {len(values)})"
            )

    for col in config["demographics"]["categorical"]:
        if col in df.columns:
            counts = df[col].value_counts(dropna=False)
            pct = (counts / len(df) * 100).round(1)
            parts = [f"{idx} {n} ({pct[idx]}%)" for idx, n in counts.items()]
            lines.append(f"- **{col}**: " + "; ".join(parts))

    lines.append("")
    return lines


def scale_descriptives(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for name, spec in config["scales"].items():
        if name not in df.columns:
            continue
        values = df[name].dropna()
        items = [i for i in spec["items"] if i in df.columns]
        scored = []
        for item in items:
            scored.append(f"{item}_r" if item in (spec.get("reverse_items") or []) else item)
        scored = [c for c in scored if c in df.columns]

        rows.append(
            {
                "Variable": spec["label"],
                "n": len(values),
                "M": round(values.mean(), 2),
                "SD": round(values.std(ddof=1), 2),
                "Min": round(values.min(), 2),
                "Max": round(values.max(), 2),
                "Skew": round(stats.skew(values, bias=False), 2),
                "Kurtosis": round(stats.kurtosis(values, bias=False), 2),
                "α": round(cronbach_alpha(df[scored]), 2) if scored else np.nan,
            }
        )
    return pd.DataFrame(rows)


def correlation_matrix(df: pd.DataFrame, variables: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df[variables]
    n = len(variables)
    r_mat = pd.DataFrame(np.eye(n), index=variables, columns=variables)
    display = pd.DataFrame("—", index=variables, columns=variables)

    for i in range(n):
        for j in range(i + 1, n):
            pair = data[[variables[i], variables[j]]].dropna()
            if len(pair) < 3:
                continue
            r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
            r_mat.iloc[i, j] = r_mat.iloc[j, i] = r
            cell = f"{r:.2f}{stars(p)}"
            display.iloc[j, i] = cell
            display.iloc[i, j] = ""
    return r_mat, display


def model_variables(config: dict) -> list[str]:
    analysis = config["analysis"]
    variables = list(analysis["predictors"])
    if analysis.get("mediator"):
        variables.append(analysis["mediator"])
    if analysis.get("moderator"):
        variables.append(analysis["moderator"])
    variables += [c for c in (analysis.get("covariates") or [])]
    variables.append(analysis["outcome"])
    return list(dict.fromkeys(variables))


def mahalanobis_outliers(data: pd.DataFrame) -> tuple[int, float, pd.Series]:
    clean = data.dropna()
    cov = np.cov(clean.values, rowvar=False)
    inv_cov = np.linalg.pinv(cov)
    centred = clean.values - clean.values.mean(axis=0)
    d2 = np.einsum("ij,jk,ik->i", centred, inv_cov, centred)
    critical = stats.chi2.ppf(0.999, df=clean.shape[1])
    return int((d2 > critical).sum()), float(critical), pd.Series(d2, index=clean.index)


def assumption_report(df: pd.DataFrame, config: dict) -> tuple[list[str], object]:
    analysis = config["analysis"]
    outcome = analysis["outcome"]
    predictors = [v for v in model_variables(config) if v != outcome]
    variables = predictors + [outcome]
    present = [v for v in variables if v in df.columns]

    lines = [
        "# Assumption testing",
        "",
        f"Model specified in `config/study.yaml`: **{analysis['model']}** "
        f"predicting **{outcome}** from {', '.join(predictors)}.",
        "",
        "## 1. Missing data",
        "",
    ]

    miss = pd.DataFrame(
        {
            "Variable": present,
            "n missing": [int(df[v].isna().sum()) for v in present],
            "% missing": [round(df[v].isna().mean() * 100, 1) for v in present],
        }
    )
    lines += [miss.to_markdown(index=False), ""]
    complete = df[present].dropna()
    lines += [f"Complete cases across all model variables: **n = {len(complete)}**", ""]

    lines += ["## 2. Univariate normality", "", "Shapiro–Wilk, plus skew and kurtosis.", ""]
    rows = []
    for var in present:
        values = df[var].dropna()
        w, p = stats.shapiro(values) if 3 <= len(values) <= 5000 else (np.nan, np.nan)
        rows.append(
            {
                "Variable": var,
                "W": round(w, 3),
                "p": f"{p:.3f}" if p >= 0.001 else "<.001",
                "Skew": round(stats.skew(values, bias=False), 2),
                "Kurtosis": round(stats.kurtosis(values, bias=False), 2),
                "Within ±2": "yes"
                if abs(stats.skew(values, bias=False)) < 2
                and abs(stats.kurtosis(values, bias=False)) < 2
                else "no",
            }
        )
    lines += [pd.DataFrame(rows).to_markdown(index=False), ""]

    lines += ["## 3. Univariate outliers", "", f"Standardised scores beyond ±{Z_OUTLIER}.", ""]
    rows = []
    for var in present:
        values = df[var].dropna()
        z = (values - values.mean()) / values.std(ddof=1)
        rows.append({"Variable": var, "n outliers": int((z.abs() > Z_OUTLIER).sum())})
    lines += [pd.DataFrame(rows).to_markdown(index=False), ""]

    n_mahal, critical, _ = mahalanobis_outliers(df[present])
    lines += [
        "## 4. Multivariate outliers",
        "",
        f"Mahalanobis distance against χ²(df = {len(present)}) critical value "
        f"{critical:.2f} at p < .001: **{n_mahal} case(s) flagged**.",
        "",
    ]

    y = complete[outcome]
    X = sm.add_constant(complete[predictors])
    fitted = sm.OLS(y, X).fit()

    lines += ["## 5. Multicollinearity", "", "Variance inflation factors and tolerance.", ""]
    if len(predictors) > 1:
        rows = []
        for i, var in enumerate(X.columns):
            if var == "const":
                continue
            vif = variance_inflation_factor(X.values, i)
            rows.append({"Predictor": var, "VIF": round(vif, 2), "Tolerance": round(1 / vif, 2)})
        lines += [pd.DataFrame(rows).to_markdown(index=False), ""]
        lines += ["Conventional thresholds: VIF < 10 and tolerance > .10.", ""]
    else:
        lines += ["Only one predictor in the model, so multicollinearity does not apply.", ""]

    bp_lm, bp_p, _, _ = het_breuschpagan(fitted.resid, fitted.model.exog)
    dw = durbin_watson(fitted.resid)
    w_res, p_res = stats.shapiro(fitted.resid)

    lines += [
        "## 6. Residual diagnostics",
        "",
        f"- **Homoscedasticity** (Breusch–Pagan): LM = {bp_lm:.2f}, "
        f"p = {bp_p:.3f} — {'no evidence of heteroscedasticity' if bp_p > .05 else 'assumption violated'}",
        f"- **Independence of residuals** (Durbin–Watson): {dw:.2f} "
        f"— {'acceptable' if 1.5 < dw < 2.5 else 'outside the 1.5–2.5 range'}",
        f"- **Normality of residuals** (Shapiro–Wilk): W = {w_res:.3f}, "
        f"p = {p_res:.3f} — {'acceptable' if p_res > .05 else 'departs from normality'}",
        "- **Linearity**: inspect `fig_residuals.png` and `fig_scatter_matrix.png`; "
        "residuals should show no systematic pattern around zero.",
        "",
        "## 7. Model summary",
        "",
        "Reported here only as a check that the model runs. Write the inferential "
        "results up following the PSY4401 conventions.",
        "",
        "```",
        str(fitted.summary()),
        "```",
        "",
    ]
    return lines, fitted


def make_figures(df: pd.DataFrame, config: dict, fitted) -> None:
    variables = [v for v in model_variables(config) if v in df.columns]

    ncols = min(3, len(variables))
    nrows = int(np.ceil(len(variables) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), squeeze=False)
    for ax, var in zip(axes.flat, variables):
        values = df[var].dropna()
        ax.hist(values, bins=15, color="#4C72B0", edgecolor="white")
        ax.set_title(f"{var}\nM = {values.mean():.2f}, SD = {values.std(ddof=1):.2f}", fontsize=9)
    for ax in axes.flat[len(variables) :]:
        ax.axis("off")
    fig.suptitle("Distribution of composite scores", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "fig_histograms.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].scatter(fitted.fittedvalues, fitted.resid, alpha=0.6, s=18, color="#4C72B0")
    axes[0].axhline(0, color="grey", linestyle="--", linewidth=1)
    axes[0].set_xlabel("Fitted values")
    axes[0].set_ylabel("Residuals")
    axes[0].set_title("Residuals vs fitted")
    sm.qqplot(fitted.resid, line="s", ax=axes[1], markersize=4, alpha=0.6)
    axes[1].set_title("Normal Q–Q plot of residuals")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "fig_residuals.png", dpi=150)
    plt.close(fig)

    subset = df[variables].dropna()
    n = len(variables)
    fig, axes = plt.subplots(n, n, figsize=(2.2 * n, 2.2 * n), squeeze=False)
    for i in range(n):
        for j in range(n):
            ax = axes[i][j]
            if i == j:
                ax.hist(subset[variables[i]], bins=12, color="#DD8452", edgecolor="white")
            else:
                ax.scatter(subset[variables[j]], subset[variables[i]], s=8, alpha=0.5,
                           color="#4C72B0")
            if i == n - 1:
                ax.set_xlabel(variables[j], fontsize=8)
            if j == 0:
                ax.set_ylabel(variables[i], fontsize=8)
            ax.tick_params(labelsize=6)
    fig.suptitle("Linearity check across model variables", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "fig_scatter_matrix.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PROCESSED_DIR / "analysis_sample.csv")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"{args.input} not found. Run scripts/prepare_data.py first.")

    config = load_config()
    ensure_dirs()
    df = pd.read_csv(args.input)

    desc_lines = ["# Descriptive statistics", ""] + describe_sample(df, config)
    table = scale_descriptives(df, config)
    desc_lines += ["## Scale descriptives and reliability", "", table.to_markdown(index=False), ""]

    variables = [v for v in model_variables(config) if v in df.columns]
    r_mat, display = correlation_matrix(df, variables)
    r_mat.round(3).to_csv(OUTPUT_DIR / "correlations.csv")

    corr_lines = [
        "# Intercorrelations",
        "",
        display.to_markdown(),
        "",
        "`* p < .05, ** p < .01, *** p < .001` (two-tailed Pearson, pairwise deletion)",
        "",
    ]
    (OUTPUT_DIR / "correlations.md").write_text("\n".join(corr_lines) + "\n")

    desc_lines += ["## Intercorrelations", "", display.to_markdown(), "",
                   "`* p < .05, ** p < .01, *** p < .001`", ""]
    (OUTPUT_DIR / "descriptives.md").write_text("\n".join(desc_lines) + "\n")

    assumption_lines, fitted = assumption_report(df, config)
    (OUTPUT_DIR / "assumptions.md").write_text("\n".join(assumption_lines) + "\n")

    make_figures(df, config, fitted)

    print(table.to_string(index=False))
    print()
    print(display.to_string())
    print(f"\nWrote descriptives, correlations, assumptions and 3 figures to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
