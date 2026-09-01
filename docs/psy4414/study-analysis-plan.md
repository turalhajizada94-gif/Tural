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

## What your SPSS dataset actually contains

Read from the 176-variable list in your SPSS Variable View. The counts below are
arithmetically consistent with the full list, so the block structure is solid even
though the variable names themselves are uninformative.

| Rows | Variables | What it is |
| --- | --- | --- |
| 1–17 | 17 | Standard Qualtrics metadata (`StartDate` … `UserLanguage`) |
| 18–21 | 4 | `QID12784…` — most likely consent or a screening block |
| 22–41 | 20 | `Q1`, `Q2`, `Q3`, `Q4_1`–`Q4_15`, `Q5`, `Q6` — demographics plus a 15-option question |
| 42–62 | 21 | `Q1.0`–`Q21` — a 21-item instrument |
| 63–122 | **60** | `BFI_Q1_`–`BFI_Q60_` — a 60-item Big Five inventory |
| 123–149 | 27 | `Part_A._1`–`Part_C._9` — a three-part, 9-items-each measure |
| 150–171 | **22** | `Q2.1`–`Q23` — a 22-item instrument |
| 172 | 1 | `Q_DataPolicyViolations` — Qualtrics fraud/bot detection |
| 173–176 | 4 | `FL_11_DO_…` — survey flow display-order variables from the randomiser |

Four things follow from this.

**This is a shared battery, not your survey.** Five distinct instrument blocks are
present, far more than your two measures. That fits the pre-registration, which
lists Helena Selber, Remedios Bagang and Katerina Karamelis as joint recruiters —
several students' projects were evidently combined into one Qualtrics survey. Most
of these 176 columns are not yours, and your first job is working out which are.

**The 22-item block at rows 150–171 is very probably your NAQ-R.** It is the only
22-variable block, and the NAQ-R has exactly 22 items.

**There is a 60-item Big Five inventory where your 4-item Mini-IPIP6 should be.**
This is the serious one, and it is discussed as its own point below.

**Two variables you should use that you probably were not planning to.**
`Q_DataPolicyViolations` is Qualtrics' own fraud and bot detection — a genuine data
cleaning input, and a defensible exclusion criterion worth reporting.
`FL_11_DO_…` records the randomised block display order, which is exactly the
counterbalancing your pre-registration described; it lets you actually test for
order effects rather than just asserting you controlled for them.

### Resolve the column names before anything else

Export tags like `Q4_11` and `Q13.0` say nothing about what was asked. The
question text does, and it is already in your files: row 2 of a Qualtrics CSV
export, and the variable **labels** of your `.sav`. Run:

```bash
python scripts/inspect_export.py
```

This writes `output/codebook.md`, pairing every column with its question text,
grouping consecutive columns into blocks, and matching known instruments by
wording. To pin down a single item:

```bash
python scripts/inspect_export.py --search "level of competence"
```

If you would rather stay in SPSS, `DISPLAY DICTIONARY.` prints names, labels and
value labels for the whole file.

Note also that names like `Q1.0`, `Q5.1` and `Q13.0` are SPSS renaming duplicates
on import, because the export contained repeated tags across blocks. Be careful you
are picking up items from the block you intend.

---

## Six things to settle with your supervisor before you write

These came out of reading the three submissions side by side. Each one could cost
marks under the rubric's "Knowledge and Alignment" criterion, which rewards
results that are explicitly linked to the stated objectives.

### 1. Your moderator may not be the measure you pre-registered

You pre-registered the **4-item Mini-IPIP6 Openness subscale** on a 7-point scale
(Sibley, 2012). Your dataset contains a **60-item** `BFI_Q1_`–`BFI_Q60_` block. Sixty
items is the length of the BFI-2 (Soto & John, 2017), whose Open-Mindedness domain
is 12 items on a 5-point scale. Four consecutive Openness items are not obviously
anywhere in the list.

Three possibilities, and you need to establish which before you compute anything:

1. **The BFI-2 replaced the Mini-IPIP6.** Then your moderator is a 12-item domain
   on a different response scale, your Method section is wrong as written, and this
   is a change of measure to discuss with your supervisor — including whether it
   belongs in the Substantial Deviation Events Declaration.
2. **The BFI block belongs to another student** in the shared battery and your
   Mini-IPIP6 items are inside one of the unidentified blocks (rows 22–62 or
   123–149). Then nothing has changed and you just need the right column names.
3. **The Mini-IPIP6 was never administered.** That is a major deviation and needs
   raising with your supervisor immediately.

`scripts/inspect_export.py` distinguishes these in one run: it searches for the
distinctive Mini-IPIP6 wording ("vivid imagination", "not interested in abstract
ideas") and for BFI-2 wording ("I am someone who…"), and reports which blocks
matched. Until this is settled, the `openness` scale in `config/study.yaml` is
deliberately left as a placeholder rather than guessing.

This is the single highest-priority item on this page. Everything downstream —
the reliability you report, the mean-centring, the interaction term, the simple
slopes — depends on knowing which items form the moderator.

### 2. Your H2 is worded two different ways

The Introduction and the pre-registration both state H2 **directionally**: the
relationship will be *"significantly weaker"* at higher Openness. The ethics
application states it **non-directionally**: the relationship *"will significantly
differ based on levels of Openness (low, average, and high)"*.

This matters because the Results Section FAQ specifically warns that a mismatch
between your hypothesis, your design and your analysis can be considered in
grading, and asks you to confirm the wording with your supervisor. It also decides
whether a one- or two-tailed test is defensible. Pick one wording, use it on the
first page of your Results, and make sure the Introduction matches.

### 3. Full-time only, or full-time and part-time?

The pre-registration and the ethics application both say *"full-time or
part-time"*. Your supervisor annotated the ethics application twice with *"We will
be focused on full-time only"* (comments 5.1 and 9.1).

If full-time only is the rule, it is an eligibility screen that has to appear as a
line in your participant flow, and it will reduce your N. `config/study.yaml` has
a `categorical_eligibility` rule ready for this, currently `enabled: false` —
switch it on and set the column and codes once you have decided.

### 4. Expect the interaction to be hard to detect, and say so in advance

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

### 5. Skip logic means you should expect item-level missingness

The ethics application says skip logic was enabled so participants could bypass
any question. Your supervisor's comment 4.1 pushes the other way: *"Participants
are required to answer all questions, otherwise, we will not have valid data to
analyse."*

Whichever was implemented, check the actual missingness in your export. If skip
logic was live, Little's MCAR does real work in your Data Cleaning subsection, and
your pre-registered rule (listwise under 5%, multiple imputation over) decides what
happens next. `scripts/analyse.py` runs Little's MCAR and tells you which branch
your data falls on.

### 6. Do not put the NAQ-R or Mini-IPIP6 in your appendix

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
python scripts/inspect_export.py    # first: work out which columns are yours
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
