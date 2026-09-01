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
| Moderator | Openness to Experience — Mini-IPIP6 Openness subscale, 4 items, 7-point Likert, **mean-centred** |
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

## Five things to settle with your supervisor before you write

These came out of reading the three submissions side by side. Each one could cost
marks under the rubric's "Knowledge and Alignment" criterion, which rewards
results that are explicitly linked to the stated objectives.

### 1. Your H2 is worded two different ways

The Introduction and the pre-registration both state H2 **directionally**: the
relationship will be *"significantly weaker"* at higher Openness. The ethics
application states it **non-directionally**: the relationship *"will significantly
differ based on levels of Openness (low, average, and high)"*.

This matters because the Results Section FAQ specifically warns that a mismatch
between your hypothesis, your design and your analysis can be considered in
grading, and asks you to confirm the wording with your supervisor. It also decides
whether a one- or two-tailed test is defensible. Pick one wording, use it on the
first page of your Results, and make sure the Introduction matches.

### 2. Full-time only, or full-time and part-time?

The pre-registration and the ethics application both say *"full-time or
part-time"*. Your supervisor annotated the ethics application twice with *"We will
be focused on full-time only"* (comments 5.1 and 9.1).

If full-time only is the rule, it is an eligibility screen that has to appear as a
line in your participant flow, and it will reduce your N. `config/study.yaml` has
a `categorical_eligibility` rule ready for this, currently `enabled: false` —
switch it on and set the column and codes once you have decided.

### 3. Expect the interaction to be hard to detect, and say so in advance

Your own power analysis is candid about this: Dåderman and Basinska (2021)
reported interaction effects around *f*² ≈ 0.016, which would need N > 606. You
powered instead for a medium effect (*f*² = 0.15, power .95, α .05), giving a
minimum N = 107. With 180 responses you are comfortably powered for the **main
effects**, and underpowered for a small interaction.

So H1 is a fair test, and a non-significant H2 would be an entirely expected
outcome rather than a failure. The FAQ is explicit that non-significant findings
are reported objectively and in full. Do not go looking for a significant
interaction; report what you find and let the Discussion handle the power
limitation.

### 4. Skip logic means you should expect item-level missingness

The ethics application says skip logic was enabled so participants could bypass
any question. Your supervisor's comment 4.1 pushes the other way: *"Participants
are required to answer all questions, otherwise, we will not have valid data to
analyse."*

Whichever was implemented, check the actual missingness in your export. If skip
logic was live, Little's MCAR does real work in your Data Cleaning subsection, and
your pre-registered rule (listwise under 5%, multiple imputation over) decides what
happens next. `scripts/analyse.py` runs Little's MCAR and tells you which branch
your data falls on.

### 5. Do not put the NAQ-R or Mini-IPIP6 in your appendix

Your ethics application listed the NAQ-R as Appendix A and the Mini-IPIP6 as
Appendix B, which was right for that submission. The Journal Manuscript guidelines
say the opposite: *"Do not include already published measures in the appendix as
this can be a breach of copyright. Only include the scales used for your study if
they are novel measures you have developed."* Both of your measures are published,
so neither goes in the manuscript appendix.

---

## Two more things carried over from your earlier submissions

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
python scripts/prepare_data.py
python scripts/analyse.py
python scripts/hypothesis_tests.py
```

### Watch the Openness reliability

The Mini-IPIP6 Openness subscale is only four items, so its Cronbach's alpha may
well fall below .70. The FAQ says to contact your supervisor **before** running
your analysis if that happens, not after. `method_section_stats.md` flags it
explicitly if it does.

### And remember where the output file has to come from

The pre-registration commits you to PROCESS in SPSS v30, and the unit expects an
output file containing SPSS output *and syntax boxes*. This pipeline is a
cross-check against that, not a substitute for it. Run both, compare the numbers,
and investigate any discrepancy — see
[the export guide](qualtrics-export-guide.md#part-4--important-the-submitted-output-file-most-likely-needs-to-be-spss).
