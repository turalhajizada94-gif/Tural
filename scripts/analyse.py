"""Produce the statistics behind each Results section subsection.

Outputs are grouped to match where the unit requires each statistic to be
reported, which is not the same as where it feels natural to put it. Per the
Results Section FAQ, Cronbach's alpha for validated scales and the sample
demographics belong in the METHOD, while the Preliminary Analyses subsection
describes the study VARIABLES.

Reads data/processed/analysis_sample.csv and writes to output/:

    method_section_stats.md   demographics + reliabilities  -> Method, not Results
    assumption_testing.md     -> Results subsection 2
    preliminary_analyses.md   variable descriptives + correlations -> subsection 3
    inferential_statistics.md effect sizes and CIs -> subsection 4 (scaffold only)
    correlations.csv          machine-readable matrix
    fig_histograms.png        distribution of each composite
    fig_residuals.png         residuals vs fitted, and a normal Q-Q plot
    fig_scatter_matrix.png    linearity check across model variables

Every table is a working output. Reformat to APA 7th before it goes in the
manuscript.

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

from common import (
    OUTPUT_DIR,
    PROCESSED_DIR,
    cronbach_alpha,
    ensure_dirs,
    load_config,
    reverse_score,
)

Z_OUTLIER = 3.29
ALPHA_FLOOR = 0.70

APA_NOTE = (
    "> Working output. Reformat as an APA 7th table before it goes in the "
    "manuscript, and reference it in the text."
)


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
    rows = []
    for spec in config["scales"].values():
        block = scored_items(df, spec)
        if block.empty or block.shape[1] < 2:
            continue
        alpha = cronbach_alpha(block)
        rows.append(
            {
                "Scale": spec["label"],
                "Items": block.shape[1],
                "α": round(alpha, 2),
                "Below .70": "YES — contact supervisor" if alpha < ALPHA_FLOOR else "no",
            }
        )
    return pd.DataFrame(rows)


def variable_descriptives(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for name, spec in config["scales"].items():
        if name not in df.columns:
            continue
        values = df[name].dropna()
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


def correlation_details(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    """Pairwise correlations with 95% CIs, via the Fisher z transformation.

    APA 7th expects effect sizes with confidence intervals; r is itself the effect
    size, so the CI is what needs adding.
    """
    rows = []
    for i, first in enumerate(variables):
        for second in variables[i + 1 :]:
            pair = df[[first, second]].dropna()
            n = len(pair)
            if n < 4:
                continue
            r, p = stats.pearsonr(pair[first], pair[second])
            z = np.arctanh(r)
            se = 1 / np.sqrt(n - 3)
            lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
            rows.append(
                {
                    "Pair": f"{first} – {second}",
                    "n": n,
                    "r": round(r, 2),
                    "95% CI": f"[{lo:.2f}, {hi:.2f}]",
                    "p": f"{p:.3f}" if p >= 0.001 else "<.001",
                }
            )
    return pd.DataFrame(rows)


def inferential_scaffold(df: pd.DataFrame, config: dict) -> tuple[list[str], object]:
    """OLS with the effect sizes and confidence intervals APA 7th requires.

    This is a scaffold, not your reported analysis: the model has to follow the
    data analysis plan agreed with your supervisor. Mediation and moderation in
    particular need bootstrapped indirect effects (e.g. PROCESS).
    """
    analysis = config["analysis"]
    outcome = analysis["outcome"]
    predictors = [v for v in model_variables(config) if v != outcome and v in df.columns]

    complete = df[predictors + [outcome]].dropna()
    y = complete[outcome]
    X = sm.add_constant(complete[predictors])
    fit = sm.OLS(y, X).fit()

    r2, adj_r2 = fit.rsquared, fit.rsquared_adj
    f2 = r2 / (1 - r2) if r2 < 1 else np.nan

    z = complete.apply(lambda c: (c - c.mean()) / c.std(ddof=1))
    std_fit = sm.OLS(z[outcome], sm.add_constant(z[predictors])).fit()

    ci = fit.conf_int()
    rows = []
    for name in predictors:
        rows.append(
            {
                "Predictor": name,
                "b": round(fit.params[name], 3),
                "SE": round(fit.bse[name], 3),
                "95% CI for b": f"[{ci.loc[name, 0]:.3f}, {ci.loc[name, 1]:.3f}]",
                "β": round(std_fit.params[name], 3),
                "t": round(fit.tvalues[name], 2),
                "p": f"{fit.pvalues[name]:.3f}" if fit.pvalues[name] >= 0.001 else "<.001",
            }
        )

    lines = [
        "# Inferential statistics (scaffold)",
        "",
        f"**Model in `config/study.yaml`:** {analysis['model']} — {outcome} regressed on "
        f"{', '.join(predictors)} (n = {len(complete)}).",
        "",
        "> This runs an ordinary least squares model so the effect sizes and "
        "confidence intervals are in front of you. It is **not** your reported "
        "analysis. Use the model agreed in your data analysis plan, and for "
        "mediation or moderation use PROCESS or an equivalent with bootstrapped "
        "indirect effects.",
        "",
        "## Overall model",
        "",
        f"- F({int(fit.df_model)}, {int(fit.df_resid)}) = {fit.fvalue:.2f}, "
        f"p = {fit.f_pvalue:.4f}" if fit.f_pvalue >= 0.0001 else
        f"- F({int(fit.df_model)}, {int(fit.df_resid)}) = {fit.fvalue:.2f}, p < .001",
        f"- R² = {r2:.3f}, adjusted R² = {adj_r2:.3f}",
        f"- Cohen's f² = {f2:.3f} "
        f"({'small' if f2 < 0.15 else 'medium' if f2 < 0.35 else 'large'} by conventional benchmarks)",
        "",
        "## Coefficients",
        "",
        pd.DataFrame(rows).to_markdown(index=False),
        "",
        APA_NOTE,
        "",
        "Report non-significant predictors as fully as significant ones, and keep "
        "interpretation of what the findings *mean* for the Discussion.",
        "",
    ]
    return lines, fit


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

    # --- Method section material (NOT the Results) ---------------------------
    alphas = reliability_table(df, config)
    method_lines = [
        "# Statistics that belong in the METHOD section",
        "",
        "> Per the Results Section FAQ, both of these are reported in the Method, "
        "not the Results. Cronbach's alpha moves into the Results only if your "
        "study develops or refines a scale; demographics move only if they bear "
        "directly on hypothesis testing.",
        "",
        "## Reliability of scales — Method, Measures subsection",
        "",
        alphas.to_markdown(index=False),
        "",
    ]
    low = alphas[alphas["α"] < ALPHA_FLOOR] if not alphas.empty else alphas
    if not low.empty:
        method_lines += [
            f"**Contact your supervisor before running your analysis.** "
            f"{len(low)} scale(s) fell below the conventionally accepted .70: "
            + ", ".join(low["Scale"]),
            "",
        ]
    method_lines += ["## Sample description — Method, Participants subsection", ""]
    method_lines += describe_sample(df, config)[2:]
    (OUTPUT_DIR / "method_section_stats.md").write_text("\n".join(method_lines) + "\n")

    # --- Results subsection 2: Assumption Testing ----------------------------
    assumption_lines, fitted = assumption_report(df, config)
    (OUTPUT_DIR / "assumption_testing.md").write_text("\n".join(assumption_lines) + "\n")

    # --- Results subsection 3: Preliminary Analyses --------------------------
    descriptives = variable_descriptives(df, config)
    variables = [v for v in model_variables(config) if v in df.columns]
    r_mat, display = correlation_matrix(df, variables)
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
        "`* p < .05, ** p < .01, *** p < .001` (two-tailed Pearson, pairwise deletion)",
        "",
        "### With confidence intervals",
        "",
        correlation_details(df, variables).to_markdown(index=False),
        "",
        "> Correlations belong here only if they are preliminary to a hypothesised "
        "model. If the relationships between variables *are* your hypothesis test, "
        "move them to Inferential Statistics. Check the correlation type suits the "
        "measurement level of your variables.",
        "",
        APA_NOTE,
        "",
    ]
    (OUTPUT_DIR / "preliminary_analyses.md").write_text("\n".join(prelim_lines) + "\n")

    # --- Results subsection 4: Inferential Statistics ------------------------
    inferential_lines, _ = inferential_scaffold(df, config)
    (OUTPUT_DIR / "inferential_statistics.md").write_text("\n".join(inferential_lines) + "\n")

    make_figures(df, config, fitted)

    print("Reliabilities (-> Method):")
    print(alphas.to_string(index=False))
    print("\nStudy variable descriptives (-> Preliminary Analyses):")
    print(descriptives.to_string(index=False))
    print("\nIntercorrelations:")
    print(display.to_string())
    print(f"\nWrote 4 reports, correlations.csv and 3 figures to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
