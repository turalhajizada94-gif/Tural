# The study, and the analysis plan you committed to

*The Shield of Creativity: Openness Moderates the Impact of ESL Status on
Workplace Bullying* — Tural Hajizada (31843069), GDPA, Monash University.
Supervisor: Chiao Kee Lim.

Compiled from the PSY4412 pre-registration, the ethics application, and the
Milestone 1 Introduction (all three with marker feedback). `config/study.yaml` is
configured from these documents, so the pipeline runs the analysis you
pre-registered rather than a generic one.

---

## The design

| Element | Specification |
| --- | --- |
| Study type | Quasi-experimental, cross-sectional, self-report questionnaire |
| Predictor (IV) | ESL status — "Is English your first language?" Yes/No, dummy coded **0 = native, 1 = ESL** |
| Outcome (DV) | Workplace bullying — NAQ-R **sum** score, 22 items, 1 = Never to 5 = Daily, last six months |
| Moderator | Openness — pre-registered as Mini-IPIP6 (4 items, 7-point); **actually administered as the BFI-2 Open-Mindedness domain** (12 items, 5-point), **mean-centred** |
| Covariate | Gender (the only pre-registered covariate; age is demographic, not a covariate) |
| Recruitment | Prolific (paid) and LinkedIn (snowball) |
| Eligibility | Aged 25+, employed in Australia — see the conflict flagged below |
| Software | SPSS v30 with Hayes' PROCESS macro |

### The hypotheses

**H1 (main effect).** ESL speakers will report significantly higher NAQ-R scores
than native English speakers. → Independent samples *t*-test.

**H2 (moderation).** Openness will moderate the ESL–bullying relationship, such
that the positive relationship is significantly weaker at higher Openness. →
Hierarchical multiple regression, PROCESS Model 1:

1. **Step 1** — covariate (Gender)
2. **Step 2** — predictor (ESL, dummy coded) and moderator (Openness, mean-centred)
3. **Step 3** — interaction term (ESL × Openness)

Supported if the interaction is significant at *p* < .05; significant
interactions probed with simple slopes at −1 SD, the mean, and +1 SD of Openness.

### The pre-registered assumption checks

| Assumption | Pre-registered method | Threshold |
| --- | --- | --- |
| Missing data | Little's MCAR | Listwise deletion if < 5%, multiple imputation if greater |
| Univariate outliers | Box plots | — |
| Multivariate outliers | Mahalanobis and Cook's distance | — |
| Normality | Skewness and kurtosis, Shapiro–Wilk | **standardised value ±1.96** |
| Autocorrelation | Durbin–Watson | — |
| Normality/linearity of residuals | Normal P–P plot | — |
| Homoscedasticity | Scatterplots of residuals | — |
| Multicollinearity | Variance inflation factors | **VIF < 4** |

These thresholds are in `config/study.yaml` under `thresholds`, which is why the
pipeline reports ±1.96 standardised skew and VIF < 4 rather than the more common
±2 and VIF < 10. Report against what you pre-registered.

---
## What your dataset actually contains

Resolved from the SPSS data dictionary (`DISPLAY DICTIONARY`, 176 variables,
1 September 2026 export). The column names are now in `config/study.yaml`, so
the pipeline reads your real data without further mapping.

| Positions | Variables | Content |
| --- | --- | --- |
| 1–17 | 17 | Qualtrics metadata |
| 18 | 1 | `QID127848236` — consent (1 = Agree, 2 = Disagree) |
| 19–21 | 3 | Screeners: Australian citizen/PR, aged 25–65, fluent in English (each 1 = Yes) |
| 22–24 | 3 | `Q1` age code, `Q2` employment status, `Q3` gender |
| 25–39 | 15 | `Q4_1`–`Q4_15` — ethnicity, multi-select |
| 40–41 | 2 | `Q5` English proficiency, `Q6` industry |
| 42–62 | 21 | **DASS-21** — another project's measure |
| 63–122 | 60 | **BFI-2** — contains your moderator |
| 123–149 | 27 | **Short Dark Triad** (Machiavellianism, Narcissism, Psychopathy) — another project |
| 150–171 | 22 | **NAQ-R** — your outcome |
| 172 | 1 | `Q_DataPolicyViolations` (a string field, not numeric) |
| 173–176 | 4 | Block randomiser display order: MentalState, BigFiveinventory, AdditionalTendencies, NegativeActs |

### Your two measures

**Outcome — NAQ-R, positions 150–171.** All 22 items confirmed from their
wording, from "Someone withholding information which affects your performance"
through to "Threats of violence or physical or actual abuse". Coded 1 = Never,
2 = Occasionally, 3 = Monthly, 4 = Weekly, 5 = Daily, which is the correct NAQ-R
scale. Summed as pre-registered, giving a possible range of 22–110.

Note the variable names are `Q2.1`, `Q3.1`, `Q4.0`, `Q5.1`, `Q6.1`, `Q7.0` …
`Q21.0`, `Q22`, `Q23`. SPSS appended `.0`/`.1` because the export reused tags
across blocks, so `Q4` (position 45) is a DASS-21 item while `Q4.0` (position
152) is the NAQ-R item. Selecting the wrong one is an easy and silent mistake.

**Moderator — BFI-2 Open-Mindedness, 12 items.** These are BFI-2 items 5, 10,
15, 20, 25, 30, 35, 40, 45, 50, 55 and 60, which appear as `BFI_Q5_`, `BFI_Q10`,
`BFI_Q15_`, `BFI_Q20__`, `BFI_Q25__`, `BFI_Q30__`, `BFI_Q35_`, `BFI_Q40_`,
`BFI_Q45_`, `BFI_Q50__`, `BFI_Q55_`, `BFI_Q60_`. The trailing underscores vary
between one and two and are part of the actual names.

Each was verified from its question text, and the six negatively keyed items are
the standard set (5, 25, 30, 45, 50, 55): "has few artistic interests", "avoids
intellectual, philosophical discussions", "has little creativity", "has
difficulty imagining things", "thinks poetry and plays are boring", "has little
interest in abstract ideas". Response scale is 1 = Disagree strongly to
5 = Agree strongly.

---

## Seven things to settle with your supervisor before you write

### 1. Your moderator is not the measure you pre-registered — confirmed

You pre-registered the **4-item Mini-IPIP6 Openness subscale on a 7-point
scale**. The survey administered the **60-item BFI-2**, and the Mini-IPIP6
appears nowhere in the 176 variables. So your moderator is the **12-item
Open-Mindedness domain on a 5-point scale**.

This is not fatal — the BFI-2 is the better instrument, and 12 items will be more
reliable than 4 — but it is a change of measure with consequences you need to
handle deliberately:

- Your **Method section** currently describes the Mini-IPIP6 and must be rewritten.
- Your **construct** shifts slightly. Mini-IPIP6 Openness and BFI-2
  Open-Mindedness are close but not identical, and the Introduction's
  theoretical argument about cognitive flexibility should be checked against
  what Open-Mindedness actually measures.
- Ask your supervisor whether this belongs in the **Substantial Deviation Events
  Declaration**. The guidelines class a "moderate" issue as manageable and not
  requiring declaration, and "major" as including major changes to methods. A
  swapped personality instrument sits on the boundary, and this is your
  supervisor's call, not yours.
- The pre-registration's Mini-IPIP6 citation (Sibley, 2012) must be replaced
  with the BFI-2 source (Soto & John, 2017).

### 2. There are no attention checks in the dataset

Your ethics application committed to two: *"two non-intrusive attention check
questions will be embedded within the survey flow (e.g., 'Please select
Somewhat agree for this question to show you are reading carefully'), and
participants who fail these checks will be excluded from the final analysis to
preserve data quality."*

No such variables exist in the data dictionary. The only similar item is the
consent question, which asks you to select "agree" but serves a different
purpose.

Two consequences. First, a **pre-registered exclusion criterion cannot be
applied**, which needs acknowledging rather than quietly dropping. Second, you
lose your main defence against careless responding in a **paid Prolific sample**,
where that risk is highest. What remains is completion time, `Progress`, and
`Q_DataPolicyViolations` (Qualtrics' own fraud detection — note it is a *string*
field, so screen it for non-empty values rather than comparing it to a number).
Discuss with your supervisor what a defensible data-quality screen looks like now.

### 3. Your ESL variable is a five-level proficiency item, not Yes/No

The pre-registration describes asking *"Is English your first language?"*
(Yes/No). `Q5` actually asks about spoken English proficiency with five options:

| Code | Label |
| --- | --- |
| 1 | English is my first language. I have native English speaker proficiency. |
| 2 | English is not my first language. However, I have native English speaker proficiency. |
| 3 | English is not my first language. I am highly fluent in English. |
| 4 | English is not my first language. I am moderately fluent in English. |
| 5 | English is not my first language. I am not very fluent in English. |

The pipeline codes ESL = 0 for level 1 and ESL = 1 for levels 2–5, which matches
the pre-registered construct ("is English your first language"). Two things to
raise:

- **Level 2 is a genuine boundary case** — not a first language, but native
  proficiency. Under Victim Precipitation Theory your mechanism runs through
  perceived linguistic markers, so someone with native proficiency arguably is
  not exposed to the risk you theorised. A sensitivity analysis excluding or
  reclassifying level 2 would strengthen the paper.
- **You could use the full five-level variable** as an ordinal measure of
  proficiency, which is closer to your theory than a binary split. That is a
  deviation from the pre-registered analysis, so it would be a supplementary
  analysis rather than your primary test.

### 4. A range-restriction problem worth naming in the Discussion

Screener `QID127848234` asked *"Are you fluent in English?"* and non-fluent
respondents were excluded. But your hypothesis is that limited English
proficiency creates structural vulnerability to bullying — so the eligibility
criterion systematically removes the group your theory predicts is **most** at
risk.

This does not invalidate anything, but it restricts range on the predictor and
biases the ESL effect towards zero. It is a real limitation, you should say so
in the Discussion, and it is worth checking how many respondents selected `Q5`
level 4 or 5 to see how much of the range survived.

### 5. Your H2 is worded two different ways

The Introduction and the pre-registration both state H2 **directionally**: the
relationship will be *"significantly weaker"* at higher Openness. The ethics
application states it **non-directionally**: the relationship *"will
significantly differ based on levels of Openness (low, average, and high)"*.

The Results Section FAQ warns specifically that a mismatch between your
hypothesis, design and analysis can be considered in grading, and asks you to
confirm the wording with your supervisor. It also decides whether a one- or
two-tailed test is defensible. Pick one, use it on the first page of your
Results, and make the Introduction match.

### 6. Full-time only, full-time and part-time, or self-employed too?

The pre-registration and ethics application both say *"full-time or part-time"*.
Your supervisor annotated the ethics application twice with *"We will be focused
on full-time only"*. The survey then offered a **third** option nobody
anticipated: `Q2` is 1 = Employed full-time, 2 = Employed part-time,
3 = Self-employed.

Self-employed respondents are a conceptual problem for a workplace bullying
study, since many have no colleagues or supervisor. Whatever you decide becomes
a line in your participant flow. `config/study.yaml` has the full-time-only rule
ready and currently disabled.

### 7. Expect the interaction to be hard to detect, and say so in advance

Your own power analysis is candid: Dåderman and Basinska (2021) reported
interaction effects around *f*² ≈ 0.016, needing N > 606. You powered for a
medium effect (*f*² = 0.15, power .95, α .05), giving a minimum N = 107. With 180
responses you are comfortably powered for the **main effect** and underpowered
for a small interaction.

H1 is therefore a fair test, and a non-significant H2 is an expected outcome
rather than a failure. The FAQ is explicit that non-significant findings are
reported objectively and in full. Report what you find and let the Discussion
handle the power limitation.

### And one thing that would have silently corrupted your results

`Q1` (age) is stored as codes **1 to 41**, with value labels 25 to 65. The raw
code is not the age: someone coded `1` is 25 years old. Anything computed
straight from `Q1` — a mean age for your sample description, or age as a
covariate — would be wrong by exactly 24 years. The pipeline derives
`Age_years = Q1 + 24` and reports the resulting range so you can eyeball it.

The same trap appears in the DASS-21 block, stored 1–4 but labelled 0–3. That is
not your measure, but if you ever borrow those items, check the coding. Your
NAQ-R items are stored 1–5 matching Never–Daily, so they need no adjustment.

---
## Three things carried over from your earlier submissions

**Do not put the NAQ-R or the BFI-2 in your appendix.** Your ethics application
listed the NAQ-R as Appendix A and the Mini-IPIP6 as Appendix B, which was right
for that submission. The Journal Manuscript guidelines say the opposite: *"Do not
include already published measures in the appendix as this can be a breach of
copyright. Only include the scales used for your study if they are novel measures
you have developed."* Both measures you actually used are published, so neither
belongs in the manuscript appendix.

**Your data cleaning has to mention the IP addresses.** Your supervisor corrected
the ethics claim that IP addresses are never collected: *"Qualtrics record IP
addresses of all the submissions. However, we delete this in the data cleaning
stage."* That deletion is a real data-cleaning step and belongs in the Data
Cleaning subsection. `scripts/prepare_data.py` performs it on import and lists the
dropped columns in `output/data_cleaning_report.md`.

**Your Statement of Contribution has co-contributors to name.** The
pre-registration lists Chiao Kee (methodology and variable selection guidance) and
Helena Selber, Remedios Bagang and Katerina Karamelis (joint recruitment via
LinkedIn). The final manuscript cannot be marked without an accurate Statement of
Contribution, so that joint recruitment needs to be described accurately.

---

## How the pipeline maps onto your Results subsections

| Subsection | Generated by | Output |
| --- | --- | --- |
| *(first page, ungraded)* aim, hypotheses, design | you | — |
| Data Cleaning | `prepare_data.py` | `participant_flow.md`, `data_cleaning_report.md` |
| Assumption Testing | `analyse.py` | `assumption_testing.md`, `fig_histograms.png`, `fig_residuals.png`, `fig_scatter_matrix.png` |
| Preliminary Analyses | `analyse.py` | `preliminary_analyses.md`, `correlations.csv` |
| Inferential Statistics | `hypothesis_tests.py` | `inferential_statistics.md`, `fig_simple_slopes.png` |
| *(Method, not Results)* reliabilities and demographics | `analyse.py` | `method_section_stats.md` |

Run order:

```bash
python scripts/inspect_export.py    # first: work out which columns are yours
python scripts/prepare_data.py
python scripts/analyse.py
python scripts/hypothesis_tests.py
```

### Reliability

Now that the moderator is the 12-item BFI-2 Open-Mindedness domain rather than a
4-item subscale, its Cronbach's alpha is much less likely to be a problem. The
pipeline still checks: if any scale falls below .70, `method_section_stats.md`
says so explicitly, and the FAQ requires you to contact your supervisor **before**
running the analysis rather than after.

Both alphas belong in the **Method**, Measures subsection — not the Results —
because both are previously validated scales.

### And remember where the output file has to come from

The pre-registration commits you to PROCESS in SPSS v30, and the unit expects an
output file containing SPSS output *and syntax boxes*. This pipeline is a
cross-check against that, not a substitute for it. Run both, compare the numbers,
and investigate any discrepancy — see
[the export guide](qualtrics-export-guide.md#part-4--important-the-submitted-output-file-most-likely-needs-to-be-spss).
