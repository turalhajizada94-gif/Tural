"""Hypothesis tests, following the pre-registered analysis plan.

H1 (main effect)
    Independent samples t-test comparing NAQ-R scores between ESL and native
    English speakers, with Levene's test, Welch's correction and Cohen's d.

H2 (moderation)
    Hierarchical multiple regression equivalent to Hayes' PROCESS Model 1:
        Step 1  covariate (Gender)
        Step 2  predictor (ESL, dummy coded) and moderator (Openness, mean-centred)
        Step 3  interaction term (ESL x Openness)
    Significant interactions are probed with simple slopes at -1 SD, the mean,
    and +1 SD of Openness.

Writes output/inferential_statistics.md and output/fig_simple_slopes.png.

**This is a cross-check, not your submitted analysis.** The pre-registration
specifies the PROCESS macro in SPSS v30, and the unit expects an output file
containing SPSS output and syntax. Run it in SPSS, then compare against these
numbers; a discrepancy means one of the two has a data-handling error worth
finding.

Usage:
    python scripts/hypothesis_tests.py
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

from common import OUTPUT_DIR, PROCESSED_DIR, build_model_frame, ensure_dirs, load_config


def fmt_p(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else "<.001"


def cohens_d(group_a: pd.Series, group_b: pd.Series) -> tuple[float, float, float]:
    """Cohen's d for independent groups with an approximate 95% CI."""
    n1, n2 = len(group_a), len(group_b)
    s_pooled = np.sqrt(
        ((n1 - 1) * group_a.var(ddof=1) + (n2 - 1) * group_b.var(ddof=1)) / (n1 + n2 - 2)
    )
    d = (group_a.mean() - group_b.mean()) / s_pooled
    se = np.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
    return d, d - 1.96 * se, d + 1.96 * se


def test_h1(df: pd.DataFrame, config: dict) -> list[str]:
    spec = config["analysis"]
    outcome, predictor = spec["outcome"], spec["predictor"]
    labels = {
        int(k): v
        for k, v in ((config.get("derived") or {}).get(predictor, {}).get("levels") or {}).items()
    }

    data = df[[outcome, predictor]].apply(pd.to_numeric, errors="coerce").dropna()
    native = data.loc[data[predictor] == 0, outcome]
    esl = data.loc[data[predictor] == 1, outcome]

    lines = [
        "## H1 — Main effect of ESL status",
        "",
        "> *Individuals who identify as ESL speakers will report significantly "
        "higher scores on the NAQ-R compared to native English speakers.*",
        "",
    ]

    if len(native) < 2 or len(esl) < 2:
        return lines + ["Not enough cases in one or both groups to run the test.", ""]

    groups = pd.DataFrame(
        {
            "Group": [labels.get(0, "Native"), labels.get(1, "ESL")],
            "n": [len(native), len(esl)],
            "M": [round(native.mean(), 2), round(esl.mean(), 2)],
            "SD": [round(native.std(ddof=1), 2), round(esl.std(ddof=1), 2)],
        }
    )

    lev_w, lev_p = stats.levene(native, esl, center="mean")
    equal_var = lev_p > 0.05
    t_stat, p_val = stats.ttest_ind(esl, native, equal_var=equal_var)
    d, d_lo, d_hi = cohens_d(esl, native)

    if equal_var:
        df_denom = len(native) + len(esl) - 2
    else:
        v1, v2 = native.var(ddof=1) / len(native), esl.var(ddof=1) / len(esl)
        df_denom = (v1 + v2) ** 2 / (
            v1**2 / (len(native) - 1) + v2**2 / (len(esl) - 1)
        )

    diff = esl.mean() - native.mean()
    se_diff = diff / t_stat if t_stat != 0 else np.nan
    t_crit = stats.t.ppf(0.975, df_denom)

    lines += [
        groups.to_markdown(index=False),
        "",
        f"**Levene's test** for equality of variances: F = {lev_w:.2f}, p = {fmt_p(lev_p)} — "
        + (
            "equal variances assumed, Student's t reported."
            if equal_var
            else "equal variances **not** assumed, Welch's correction applied."
        ),
        "",
        f"**t({df_denom:.1f}) = {t_stat:.2f}, p = {fmt_p(p_val)}** (two-tailed)",
        "",
        f"- Mean difference (ESL − native) = {diff:.2f}, "
        f"95% CI [{diff - t_crit * se_diff:.2f}, {diff + t_crit * se_diff:.2f}]",
        f"- Cohen's d = {d:.2f}, 95% CI [{d_lo:.2f}, {d_hi:.2f}] "
        f"({'negligible' if abs(d) < 0.2 else 'small' if abs(d) < 0.5 else 'medium' if abs(d) < 0.8 else 'large'})",
        "",
        "**H1 was "
        + ("supported" if p_val < 0.05 and diff > 0 else "not supported")
        + "** on these data"
        + (
            ", though note the difference runs opposite to the predicted direction."
            if p_val < 0.05 and diff < 0
            else "."
        ),
        "",
        "> The hypothesis is directional but this is a two-tailed test, which is the "
        "conservative choice. Confirm with your supervisor which you should report.",
        "",
    ]
    return lines


def test_h2(data: pd.DataFrame, info: dict, config: dict) -> tuple[list[str], dict | None]:
    spec = config["analysis"]
    outcome = info["outcome"]
    predictor = info["predictor"]
    moderator_col = info["moderator_col"]
    interaction = info["interaction"]
    covariates = [c for c in info["design"] if c not in (predictor, moderator_col)]

    steps = {
        "Step 1: covariate(s)": covariates,
        "Step 2: + predictor and moderator": covariates + [predictor, moderator_col],
        "Step 3: + interaction": covariates + [predictor, moderator_col, interaction],
    }

    needed = list(dict.fromkeys(covariates + [predictor, moderator_col, interaction, outcome]))
    complete = data[needed].dropna().astype(float)

    lines = [
        "## H2 — Openness as a moderator",
        "",
        "> *Openness to Experience will moderate the relationship between ESL "
        "status and workplace bullying, such that the positive relationship will "
        "be significantly weaker at higher levels of Openness.*",
        "",
        f"Hierarchical multiple regression, n = {len(complete)}. "
        f"Openness was mean-centred; ESL was dummy coded 0 = native, 1 = ESL. "
        f"Gender dummies are relative to the reference level "
        f"`{info['dummy_reference'].get('Gender', 'n/a')}`.",
        "",
        "### Model summary",
        "",
    ]

    rows = []
    fits = {}
    previous = None
    for label, predictors in steps.items():
        if not predictors:
            continue
        X = sm.add_constant(complete[predictors])
        fit = sm.OLS(complete[outcome], X).fit()
        fits[label] = fit
        delta_r2 = fit.rsquared - (previous.rsquared if previous is not None else 0.0)
        if previous is not None:
            f_change = fit.compare_f_test(previous)
            f_stat, p_change = f_change[0], f_change[1]
        else:
            f_stat, p_change = fit.fvalue, fit.f_pvalue
        rows.append(
            {
                "Step": label,
                "R²": round(fit.rsquared, 3),
                "Adj. R²": round(fit.rsquared_adj, 3),
                "ΔR²": round(delta_r2, 3),
                "F change": round(f_stat, 2) if f_stat is not None else "—",
                "p": fmt_p(p_change) if p_change is not None else "—",
            }
        )
        previous = fit

    lines += [pd.DataFrame(rows).to_markdown(index=False), ""]

    final = previous
    ci = final.conf_int()
    coef_rows = []
    for name in final.params.index:
        if name == "const":
            continue
        coef_rows.append(
            {
                "Predictor": name,
                "b": round(final.params[name], 3),
                "SE": round(final.bse[name], 3),
                "95% CI": f"[{ci.loc[name, 0]:.3f}, {ci.loc[name, 1]:.3f}]",
                "t": round(final.tvalues[name], 2),
                "p": fmt_p(final.pvalues[name]),
            }
        )

    lines += ["### Final model coefficients", "", pd.DataFrame(coef_rows).to_markdown(index=False), ""]

    interaction_p = final.pvalues.get(interaction, np.nan)
    f2 = final.rsquared / (1 - final.rsquared) if final.rsquared < 1 else np.nan
    lines += [
        f"Overall model f² = {f2:.3f}. Interaction term: b = "
        f"{final.params[interaction]:.3f}, p = {fmt_p(interaction_p)}.",
        "",
        "**H2 was "
        + ("supported" if interaction_p < 0.05 else "not supported")
        + "**: the ESL × Openness interaction was "
        + ("statistically significant" if interaction_p < 0.05 else "not statistically significant")
        + ".",
        "",
    ]

    slopes_payload = None
    lines += ["### Simple slopes", ""]
    if interaction_p < 0.05:
        lines += [
            "The pre-registered probe: the effect of ESL status at −1 SD, the mean, "
            "and +1 SD of Openness.",
            "",
        ]
    else:
        lines += [
            "The interaction was not significant, so the pre-registered plan does "
            "not call for probing. The slopes below are reported for completeness "
            "only — **do not interpret them as a moderation effect.**",
            "",
        ]

    sd = complete[moderator_col].std(ddof=1)
    slope_rows = []
    points = []
    for multiplier in spec.get("simple_slopes_sd", [-1, 0, 1]):
        shift = multiplier * sd
        shifted = complete.copy()
        shifted[moderator_col] = shifted[moderator_col] - shift
        shifted[interaction] = shifted[predictor] * shifted[moderator_col]
        cols = [c for c in final.params.index if c != "const"]
        refit = sm.OLS(shifted[outcome], sm.add_constant(shifted[cols])).fit()
        b = refit.params[predictor]
        low, high = refit.conf_int().loc[predictor]
        label = {-1: "Low (−1 SD)", 0: "Mean", 1: "High (+1 SD)"}.get(
            multiplier, f"{multiplier:+g} SD"
        )
        slope_rows.append(
            {
                "Openness": label,
                "b (ESL effect)": round(b, 3),
                "SE": round(refit.bse[predictor], 3),
                "95% CI": f"[{low:.3f}, {high:.3f}]",
                "t": round(refit.tvalues[predictor], 2),
                "p": fmt_p(refit.pvalues[predictor]),
            }
        )
        points.append((label, shift, b))

    lines += [pd.DataFrame(slope_rows).to_markdown(index=False), ""]
    slopes_payload = {
        "complete": complete,
        "fit": final,
        "sd": sd,
        "points": points,
        "significant": bool(interaction_p < 0.05),
    }
    return lines, slopes_payload


def plot_simple_slopes(payload: dict, info: dict, config: dict) -> None:
    complete = payload["complete"]
    fit = payload["fit"]
    sd = payload["sd"]
    predictor, moderator_col = info["predictor"], info["moderator_col"]
    interaction, outcome = info["interaction"], info["outcome"]

    labels = {
        int(k): v
        for k, v in ((config.get("derived") or {}).get(predictor, {}).get("levels") or {}).items()
    }
    means = complete.mean()

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    styles = {-1: ("#C44E52", "--", "Low Openness (−1 SD)"),
              0: ("#4C72B0", "-", "Mean Openness"),
              1: ("#55A868", "-.", "High Openness (+1 SD)")}

    for multiplier, (colour, style, label) in styles.items():
        ys = []
        for esl_value in (0, 1):
            row = {c: means.get(c, 0.0) for c in fit.params.index if c != "const"}
            row[predictor] = esl_value
            row[moderator_col] = multiplier * sd
            row[interaction] = esl_value * multiplier * sd
            ordered = [1.0] + [row[c] for c in fit.params.index if c != "const"]
            ys.append(float(np.dot(fit.params.values, ordered)))
        ax.plot([0, 1], ys, color=colour, linestyle=style, marker="o", label=label)

    ax.set_xticks([0, 1])
    ax.set_xticklabels([labels.get(0, "Native"), labels.get(1, "ESL")])
    ax.set_ylabel(f"Predicted {outcome} (NAQ-R)")
    ax.set_xlabel("ESL status")
    title = "Simple slopes: ESL status and workplace bullying by Openness"
    if not payload["significant"]:
        title += "\n(interaction not significant — illustrative only)"
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "fig_simple_slopes.png", dpi=150)
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
    data, info = build_model_frame(df, config)

    lines = [
        "# Inferential Statistics",
        "",
        "> **Cross-check, not the submitted analysis.** The pre-registration "
        "specifies Hayes' PROCESS Model 1 in SPSS v30, and the unit expects an "
        "output file of SPSS output with syntax. Run it there, then compare.",
        "",
    ]
    lines += test_h1(df, config)
    h2_lines, payload = test_h2(data, info, config)
    lines += h2_lines

    lines += [
        "> Working output. Reformat as APA 7th tables before they go in the "
        "manuscript, reference each in the text, report non-significant results "
        "as fully as significant ones, and keep interpretation of what the "
        "findings *mean* for the Discussion.",
        "",
    ]

    (OUTPUT_DIR / "inferential_statistics.md").write_text("\n".join(lines) + "\n")
    if payload:
        plot_simple_slopes(payload, info, config)

    print("\n".join(lines[:4]))
    print(f"Wrote {OUTPUT_DIR / 'inferential_statistics.md'} and fig_simple_slopes.png")


if __name__ == "__main__":
    main()
