"""Descriptives, reliabilities and assumption testing for the Results section.

Outputs are grouped by where the unit requires each statistic to be reported,
which is not the same as where it feels natural to put it. Per the Results
Section FAQ, Cronbach's alpha for validated scales and the sample demographics
belong in the METHOD; the Preliminary Analyses subsection describes the study
VARIABLES.

Assumption tests follow the pre-registered analysis plan: standardised skew and
kurtosis against +/-1.96, Shapiro-Wilk, Mahalanobis and Cook's distance,
Durbin-Watson, VIF < 4, and Little's MCAR to decide between listwise deletion
and multiple imputation.

Writes to output/:

    method_section_stats.md   demographics + reliabilities  -> Method, not Results
    assumption_testing.md     -> Results subsection 2
    preliminary_analyses.md   variable descriptives + correlations -> subsection 3
    correlations.csv          machine-readable matrix
    fig_histograms.png, fig_residuals.png, fig_scatter_matrix.png

Hypothesis testing lives in scripts/hypothesis_tests.py.

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
from statsmodels.stats.outliers_influence import OLSInfluence, variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

from common import (
    OUTPUT_DIR,
    PROCESSED_DIR,
    build_model_frame,
    cronbach_alpha,
    ensure_dirs,
    level_labels,
    littles_mcar_test,
    load_config,
    reverse_score,
)

APA_NOTE = (
    "> Working output. Reformat as an APA 7th table before it goes in the "
    "manuscript, and reference it in the text."
)


def thresholds(config: dict) -> dict:
    return config.get("thresholds", {})


def stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def fmt_p(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else "<.001"


def scored_items(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """The scale's items as they enter the composite, reversals applied.

    Reversal is recomputed here rather than read from the processed file, so
    reliability is correct whatever columns that file happens to carry.
    """
    reversed_items = spec.get("reverse_items") or []
    present = [item for item in spec["items"] if item in df.columns]
    block = df[present].copy()
    for item in present:
        if item in reversed_items:
            block[item] = reverse_score(block[item], spec["response_range"])
    return block


def reliability_table(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    floor = thresholds(config).get("alpha_floor", 0.70)
    rows = []
    for spec in config["scales"].values():
        block = scored_items(df, spec)
        if block.shape[1] < 2:
            continue
        alpha = cronbach_alpha(block)
        rows.append(
            {
                "Scale": spec["label"],
                "Items": block.shape[1],
                "α": round(alpha, 2),
                f"Below {floor:.2f}": "YES — contact supervisor" if alpha < floor else "no",
            }
        )
    return pd.DataFrame(rows)


def describe_sample(df: pd.DataFrame, config: dict) -> list[str]:
    lines = [f"Final analysed sample: **N = {len(df)}**", ""]

    for col in config["demographics"]["continuous"]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if values.empty:
                continue
            lines.append(
                f"- **{col}**: M = {values.mean():.2f}, SD = {values.std(ddof=1):.2f}, "
                f"range {values.min():.0f}–{values.max():.0f} (n = {len(values)})"
            )

    levels = level_labels(config)
    for col in config["demographics"]["categorical"]:
        if col not in df.columns:
            continue
        counts = df[col].value_counts(dropna=False)
        pct = (counts / len(df) * 100).round(1)
        parts = []
        for idx, n in counts.items():
            label = levels.get(col, {}).get(idx, idx)
            parts.append(f"{label} {n} ({pct[idx]}%)")
        lines.append(f"- **{col}**: " + "; ".join(parts))

    lines.append("")
    return lines


def variable_descriptives(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for name, spec in config["scales"].items():
        if name not in df.columns:
            continue
        values = pd.to_numeric(df[name], errors="coerce").dropna()
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
            }
        )
    return pd.DataFrame(rows)


def correlation_matrix(df: pd.DataFrame, variables: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df[variables]
    n = len(variables)
    r_mat = pd.DataFrame(np.eye(n), index=variables, columns=variables)
    display = pd.DataFrame("", index=variables, columns=variables)

    for i in range(n):
        display.iloc[i, i] = "—"
        for j in range(i + 1, n):
            pair = data[[variables[i], variables[j]]].dropna()
            if len(pair) < 3:
                continue
            r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
            r_mat.iloc[i, j] = r_mat.iloc[j, i] = r
            display.iloc[j, i] = f"{r:.2f}{stars(p)}"
    return r_mat, display


def correlation_details(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Pairwise correlations with 95% CIs, via the Fisher z transformation.

    APA 7th expects effect sizes with confidence intervals; r is itself the
    effect size, so the CI is what needs adding.
    """
    rows = []
    for i, first in enumerate(variables):
        for second in variables[i + 1 :]:
            pair = df[[first, second]].dropna()
            n = len(pair)
            if n < 4:
                continue
            r, p = stats.pearsonr(pair[first], pair[second])
            se = 1 / np.sqrt(n - 3)
            lo, hi = np.tanh(np.arctanh(r) - 1.96 * se), np.tanh(np.arctanh(r) + 1.96 * se)
            rows.append(
                {
                    "Pair": f"{first} – {second}",
                    "n": n,
                    "r": round(r, 2),
                    "95% CI": f"[{lo:.2f}, {hi:.2f}]",
                    "p": fmt_p(p),
                }
            )
    return pd.DataFrame(rows)


def assumption_report(data: pd.DataFrame, info: dict, config: dict) -> tuple[list[str], object]:
    limits = thresholds(config)
    zcrit = limits.get("standardised_skew_kurtosis", 1.96)
    vif_max = limits.get("vif_max", 4.0)
    cooks_max = limits.get("cooks_distance_max", 1.0)
    mahal_p = limits.get("mahalanobis_p", 0.001)

    outcome = info["outcome"]
    design = info["design"] + ([info["interaction"]] if info["interaction"] else [])
    candidates = [c for c in info["continuous"] if c in data.columns]

    # Normality, standardised skew/kurtosis and Mahalanobis distance are only
    # meaningful for continuous variables. ESL status is dichotomous by design.
    continuous = [c for c in candidates if data[c].dropna().nunique() > 2]
    dichotomous = [c for c in candidates if c not in continuous]

    lines = [
        "# Assumption Testing",
        "",
        f"Model: **{config['analysis']['model']}** — {outcome} regressed on "
        f"{', '.join(design)}.",
        "",
        "Thresholds follow the pre-registered analysis plan.",
        "",
        "## 1. Missing data",
        "",
    ]

    present = [c for c in [outcome] + design if c in data.columns]
    miss = pd.DataFrame(
        {
            "Variable": present,
            "n missing": [int(data[c].isna().sum()) for c in present],
            "% missing": [round(data[c].isna().mean() * 100, 2) for c in present],
        }
    )
    lines += [miss.to_markdown(index=False), ""]

    complete = data[present].dropna()
    overall_missing = 100 * (1 - len(complete) / len(data)) if len(data) else 0
    lines += [
        f"Complete cases across all model variables: **n = {len(complete)}** "
        f"({overall_missing:.1f}% of cases have at least one missing value).",
        "",
        "### Little's MCAR test",
        "",
    ]

    mcar = littles_mcar_test(data[continuous])
    if mcar["no_missing"]:
        lines += ["No missing values among the continuous model variables.", ""]
    else:
        lines += [
            f"χ²({mcar['df']}) = {mcar['statistic']:.2f}, p = {fmt_p(mcar['p'])}, "
            f"across {mcar['n_patterns']} missingness patterns.",
            "",
            "The pre-registered rule was listwise deletion if missingness is under "
            "5% and MCAR holds, multiple imputation otherwise. On these numbers: "
            + (
                "**listwise deletion is defensible** (MCAR not rejected)."
                if (mcar["p"] or 0) > limits.get("mcar_alpha", 0.05)
                else "**MCAR was rejected** — discuss multiple imputation with your supervisor."
            ),
            "",
        ]

    lines += [
        "## 2. Univariate normality",
        "",
        f"Standardised skew and kurtosis (statistic / SE) against ±{zcrit}, "
        "plus Shapiro–Wilk.",
        "",
    ]
    if dichotomous:
        lines += [
            "Excluded as dichotomous, where normality does not apply: "
            + ", ".join(f"`{c}`" for c in dichotomous)
            + ".",
            "",
        ]
    rows = []
    for var in continuous:
        values = data[var].dropna()
        n = len(values)
        skew = stats.skew(values, bias=False)
        kurt = stats.kurtosis(values, bias=False)
        se_skew = np.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))
        se_kurt = 2 * se_skew * np.sqrt((n * n - 1) / ((n - 3) * (n + 5)))
        z_skew, z_kurt = skew / se_skew, kurt / se_kurt
        w, p = stats.shapiro(values) if 3 <= n <= 5000 else (np.nan, np.nan)
        rows.append(
            {
                "Variable": var,
                "Skew": round(skew, 2),
                "z-skew": round(z_skew, 2),
                "Kurtosis": round(kurt, 2),
                "z-kurtosis": round(z_kurt, 2),
                f"Within ±{zcrit}": "yes" if abs(z_skew) < zcrit and abs(z_kurt) < zcrit else "NO",
                "Shapiro–Wilk W": round(w, 3),
                "p": fmt_p(p),
            }
        )
    lines += [pd.DataFrame(rows).to_markdown(index=False), ""]

    lines += [
        "## 3. Univariate outliers",
        "",
        "The pre-registered plan inspects box plots; the counts below use ±3.29 "
        "standardised scores as a numeric companion. See `fig_histograms.png`.",
        "",
    ]
    rows = []
    for var in continuous:
        values = data[var].dropna()
        z = (values - values.mean()) / values.std(ddof=1)
        rows.append(
            {
                "Variable": var,
                "n |z| > 3.29": int((z.abs() > 3.29).sum()),
                "Min z": round(z.min(), 2),
                "Max z": round(z.max(), 2),
            }
        )
    lines += [pd.DataFrame(rows).to_markdown(index=False), ""]

    y = complete[outcome]
    X = sm.add_constant(complete[design].astype(float))
    fitted = sm.OLS(y, X).fit()
    influence = OLSInfluence(fitted)

    block = complete[continuous]
    centred = block.to_numpy(dtype=float) - block.to_numpy(dtype=float).mean(axis=0)
    inv_cov = np.linalg.pinv(np.cov(block.to_numpy(dtype=float), rowvar=False))
    mahal = np.einsum("ij,jk,ik->i", centred, inv_cov, centred)
    critical = stats.chi2.ppf(1 - mahal_p, df=block.shape[1])
    cooks = influence.cooks_distance[0]

    lines += [
        "## 4. Multivariate outliers",
        "",
        f"- **Mahalanobis distance** against χ²({block.shape[1]}) = {critical:.2f} "
        f"at p < {mahal_p}: **{int((mahal > critical).sum())} case(s) flagged** "
        f"(maximum D² = {mahal.max():.2f}).",
        f"- **Cook's distance**: maximum = {cooks.max():.3f}; "
        f"**{int((cooks > cooks_max).sum())} case(s)** exceed {cooks_max}.",
        "",
    ]

    lines += ["## 5. Multicollinearity", "", f"Pre-registered threshold: VIF < {vif_max}.", ""]
    if len(design) > 1:
        rows = []
        for i, var in enumerate(X.columns):
            if var == "const":
                continue
            vif = variance_inflation_factor(X.to_numpy(dtype=float), i)
            rows.append(
                {
                    "Predictor": var,
                    "VIF": round(vif, 2),
                    "Tolerance": round(1 / vif, 2),
                    f"Under {vif_max}": "yes" if vif < vif_max else "NO",
                }
            )
        lines += [pd.DataFrame(rows).to_markdown(index=False), ""]
        if info["interaction"]:
            lines += [
                "The moderator was mean-centred before the interaction term was "
                "formed, which is what keeps the interaction's VIF interpretable.",
                "",
            ]
    else:
        lines += ["Only one predictor, so multicollinearity does not apply.", ""]

    bp_lm, bp_p, _, _ = het_breuschpagan(fitted.resid, fitted.model.exog)
    dw = durbin_watson(fitted.resid)
    w_res, p_res = stats.shapiro(fitted.resid)

    lines += [
        "## 6. Residual diagnostics",
        "",
        f"- **Homoscedasticity** (Breusch–Pagan): LM = {bp_lm:.2f}, p = {fmt_p(bp_p)} — "
        + ("no evidence of heteroscedasticity" if bp_p > 0.05 else "**assumption violated**")
        + ". The pre-registered check was a scatterplot of residuals; see `fig_residuals.png`.",
        f"- **Autocorrelation** (Durbin–Watson): {dw:.2f} — "
        + ("acceptable" if 1.5 < dw < 2.5 else "**outside the 1.5–2.5 range**"),
        f"- **Normality of residuals** (Shapiro–Wilk): W = {w_res:.3f}, p = {fmt_p(p_res)} — "
        + ("acceptable" if p_res > 0.05 else "**departs from normality**")
        + ". The pre-registered check was a normal P–P plot; the Q–Q plot in "
        "`fig_residuals.png` serves the same purpose.",
        "- **Linearity**: inspect `fig_residuals.png` and `fig_scatter_matrix.png`; "
        "residuals should show no systematic pattern around zero.",
        "",
        "## If an assumption is violated",
        "",
        "Per the Results Section FAQ: consider the data from multiple perspectives "
        "(statistical tests, visual checks, and your own understanding of the "
        "variables), and discuss it with your supervisor **before** making dramatic "
        "changes such as transformations. A non-parametric alternative may be a "
        "better solution, or you may proceed as planned and acknowledge the impact "
        "later in the manuscript.",
        "",
        APA_NOTE,
        "",
    ]
    return lines, fitted


def make_figures(data: pd.DataFrame, info: dict, fitted) -> None:
    variables = [c for c in info["continuous"] if c in data.columns]

    ncols = min(3, len(variables))
    nrows = int(np.ceil(len(variables) / ncols))
    fig, axes = plt.subplots(nrows, ncols * 2, figsize=(4 * ncols * 2, 3 * nrows), squeeze=False)
    flat = axes.flat
    for var in variables:
        values = data[var].dropna()
        ax = next(flat)
        ax.hist(values, bins=15, color="#4C72B0", edgecolor="white")
        ax.set_title(f"{var}\nM = {values.mean():.2f}, SD = {values.std(ddof=1):.2f}", fontsize=9)
        ax = next(flat)
        ax.boxplot(values, widths=0.5)
        ax.set_title(f"{var} — box plot", fontsize=9)
    for ax in flat:
        ax.axis("off")
    fig.suptitle("Distributions and box plots of model variables", fontsize=11)
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

    subset = data[variables].dropna()
    n = len(variables)
    fig, axes = plt.subplots(n, n, figsize=(2.4 * n, 2.4 * n), squeeze=False)
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
    floor = thresholds(config).get("alpha_floor", 0.70)

    # --- Method section material (NOT the Results) ---------------------------
    alphas = reliability_table(df, config)
    method_lines = [
        "# Statistics that belong in the METHOD section",
        "",
        "> Per the Results Section FAQ, both of these are reported in the Method, "
        "not the Results. Cronbach's alpha moves into the Results only if your "
        "study develops or refines a scale; demographics move only if they bear "
        "directly on hypothesis testing. This study uses two validated scales, so "
        "both stay in the Method.",
        "",
        "## Reliability of scales — Method, Measures subsection",
        "",
        alphas.to_markdown(index=False),
        "",
    ]
    low = alphas[alphas["α"] < floor] if not alphas.empty else alphas
    if not low.empty:
        method_lines += [
            f"**Contact your supervisor before running your analysis.** "
            f"{len(low)} scale(s) fell below the conventionally accepted {floor:.2f}: "
            + ", ".join(low["Scale"])
            + ". The FAQ is explicit that this conversation happens first.",
            "",
        ]
    method_lines += ["## Sample description — Method, Participants subsection", ""]
    method_lines += describe_sample(df, config)
    (OUTPUT_DIR / "method_section_stats.md").write_text("\n".join(method_lines) + "\n")

    # --- Build the pre-registered design -------------------------------------
    data, info = build_model_frame(df, config)

    # --- Results subsection 2: Assumption Testing ----------------------------
    assumption_lines, fitted = assumption_report(data, info, config)
    (OUTPUT_DIR / "assumption_testing.md").write_text("\n".join(assumption_lines) + "\n")

    # --- Results subsection 3: Preliminary Analyses --------------------------
    descriptives = variable_descriptives(df, config)
    variables = [c for c in info["continuous"] if c in data.columns]
    r_mat, display = correlation_matrix(data, variables)
    r_mat.round(3).to_csv(OUTPUT_DIR / "correlations.csv")

    prelim_lines = [
        "# Preliminary Analyses (Descriptive Statistics)",
        "",
        f"N = {len(df)}. These describe the **study variables**; the sample "
        "description sits in the Method.",
        "",
        "## Descriptive statistics",
        "",
        descriptives.to_markdown(index=False),
        "",
        "## Intercorrelations",
        "",
        display.to_markdown(),
        "",
        "`* p < .05, ** p < .01, *** p < .001` (two-tailed, pairwise deletion)",
        "",
        "### With confidence intervals",
        "",
        correlation_details(data, variables).to_markdown(index=False),
        "",
        "> ESL status is binary, so its correlations are point-biserial. "
        "Correlations belong here because they are preliminary to the "
        "hypothesised moderation model; if a relationship *is* your hypothesis "
        "test, it moves to Inferential Statistics.",
        "",
        APA_NOTE,
        "",
    ]
    (OUTPUT_DIR / "preliminary_analyses.md").write_text("\n".join(prelim_lines) + "\n")

    make_figures(data, info, fitted)

    print("Reliabilities (-> Method):")
    print(alphas.to_string(index=False))
    print("\nStudy variable descriptives (-> Preliminary Analyses):")
    print(descriptives.to_string(index=False))
    print("\nIntercorrelations:")
    print(display.to_string())
    print(f"\nWrote reports and figures to {OUTPUT_DIR}/")
    print("Next: python scripts/hypothesis_tests.py")


if __name__ == "__main__":
    main()
