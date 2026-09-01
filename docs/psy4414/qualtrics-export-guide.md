# Getting your Qualtrics data out, and which data you need

For a quantitative PSY4414 results section with ~180 surveyed respondents.

---

## Before anything else: this repository is public

Anyone can read it. Raw Qualtrics exports are identifiable human research data and
almost certainly fall under conditions in your ethics approval about storage and
access. **Do not commit them here.**

`.gitignore` is already set up to block `data/raw/`, `data/processed/`, `output/`,
and every `.csv`, `.sav` and `.xlsx` in the repository, so the default behaviour is
safe. What lives in git is the *code* that processes the data; the data itself stays
on your machine or on the university storage your ethics protocol nominates.

Check before every commit:

```bash
git status --short          # no data files should appear
git ls-files | grep -Ei '\.(csv|sav|xlsx)$'   # should return nothing
```

---

## Part 1 — Two ways to get the data across

### Route A: manual export from the Qualtrics interface (recommended)

This is the route almost every student uses, and it is entirely adequate.

1. Open your survey and go to the **Data & Analysis** tab.
2. **Export & Import → Export Data**.
3. Choose **CSV** (choose **SPSS** instead, or as well, if you plan to analyse in
   SPSS — it comes as a `.sav` with variable labels already attached).
4. Critically, select **"Use numeric values"**, not "Use choice text". The analysis
   scripts, and any reverse scoring, need numbers rather than strings like
   "Strongly agree".
5. Expand **More options** and tick:
   - **Download all fields** — so nothing is silently left out;
   - **Recode seen but unanswered questions as** `-99` (or leave blank, but be
     consistent and know which you chose);
   - **Split multi-value fields into columns** if you used any select-all questions.
6. Download, then move the file into `data/raw/` in this project.

Two things about the CSV that trip people up:

- It has **three header rows**: the machine column names, the full question text,
  and a JSON `ImportId` row. Only the first is the real header. `scripts/common.py`
  detects and strips the other two automatically, but if you open the file in Excel
  and re-save it, do not delete the wrong rows.
- Responses still in progress are excluded by default. If you want them (to
  document them in the participant flow), tick the option to include them.

### Route B: pull it via the Qualtrics API

Useful if you will re-export several times as data collection finishes, because it
removes the click-through each time.

1. In Qualtrics: **Account Settings → Qualtrics IDs → API → Generate Token**.
2. Note your **data centre** from the URL you log in at, e.g.
   `syd1.qualtrics.com` means `syd1`. Note your **survey ID** (`SV_...`) from
   **Survey → Tools → Survey ID**.
3. Put the survey ID and data centre into `config/study.yaml`.
4. Set the token as an environment variable — never paste it into a file in the repo:

```bash
export QUALTRICS_API_TOKEN='your-token-here'
python scripts/fetch_qualtrics.py
```

The script requests the export, polls until Qualtrics has built the file, unzips it
into `data/raw/`, and tells you what it wrote. Add `--format spss` for a `.sav`, or
`--include-incomplete` to pull partial responses too.

Some university Qualtrics licences disable API access for student accounts. If you
get a 401 or 403, use Route A; the rest of the pipeline is identical either way.

---

## Part 2 — Which data you actually need

A useful rule: **export everything, then let the screening rules decide what to
drop.** A re-export late in the process is painful, and the metadata you'd be
tempted to skip is exactly what the participant flow is built from.

### Required, grouped by what it is used for

| What to export | Columns | What it gives you in the results section |
| --- | --- | --- |
| Response identifier | `ResponseId` | Lets you trace and document excluded cases without using names |
| Completion metadata | `Progress`, `Finished` | The "did not complete" lines of the participant flow |
| Timing | `Duration (in seconds)`, `StartDate`, `RecordedDate` | Identifying speeders / non-genuine responding in data cleaning |
| Distribution channel | `DistributionChannel` | Lets you strip your own preview and test responses |
| Consent item | your consent question | The "did not consent" line of the flow |
| Eligibility screeners | age, location, or whatever your criteria are | The "ineligible" lines of the flow |
| Attention / validity checks | your check items | The data-cleaning justification for dropping careless responders |
| **All scale items, individually** | every item of every measure | Reverse scoring, prorating, Cronbach's alpha, composites |
| Demographics | age, gender, education, etc. | The sample description paragraph |
| Grouping or condition variables | condition, group, cohort | Any between-groups comparison |
| Embedded data | anything you set up in survey flow | Depends on your design; export it and decide later |

### Two things worth stressing

**Export item-level data, not Qualtrics' computed scores.** If you set up scoring
inside Qualtrics, ignore it for the write-up. You need the individual items because
your results section has to document reverse scoring, report internal consistency
(Cronbach's alpha), and handle missing items — none of which is possible from a
pre-computed total. Item-level data is also what makes your analysis output
verifiable, which is the point of the required output submission.

**Deliberately leave out, or delete on import, the identifying columns.** These are
`IPAddress`, `LocationLatitude`, `LocationLongitude`, `RecipientEmail`,
`RecipientFirstName`, `RecipientLastName`, and `ExternalReference`. They serve no
analytic purpose in this study and carry real re-identification risk.
`scripts/prepare_data.py` drops them on import and never writes them to the
processed file. If you recruited via a panel or an email list, that link file stays
separate and out of this project entirely.

### The number you probably don't have yet

Your 180 is the count of responses sitting in Qualtrics. The participant flow needs
the step *before* that too: how many people were invited, approached, or reached by
the advertisement. Qualtrics can give you part of it — if you distributed by email,
the **Distributions** tab reports invited, started and completed counts — but if you
recruited by advertisement or snowballing you will need your own recruitment
records. Sort this out with your supervisor before you write the flow, because
"180 people surveyed" is the end of the funnel, not the start of it.

Also expect the final analysed N to be **below** 180 once preview responses,
non-consenters, incompletes, speeders and failed attention checks come out. That
drop is not a problem; failing to account for it is.

---

## Part 3 — Running the pipeline

```bash
# one-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# edit config/study.yaml so the column names and scales match your survey

python scripts/fetch_qualtrics.py      # or drop your manual export into data/raw/
python scripts/prepare_data.py         # screening, scoring, participant flow
python scripts/analyse.py              # descriptives, correlations, assumptions
```

Outputs land in `output/`:

| File | Feeds which part of the results section |
| --- | --- |
| `participant_flow.md` | Participant flow, with a draft paragraph you can edit |
| `data_cleaning_report.md` | Data cleaning: reverse scoring, out-of-range values, prorating |
| `descriptives.md` | Sample description, scale descriptives, Cronbach's alpha |
| `correlations.md` / `.csv` | The intercorrelation matrix required for mediation/moderation |
| `assumptions.md` | Every assumption test, ready to be written up |
| `fig_histograms.png`, `fig_residuals.png`, `fig_scatter_matrix.png` | Visual assumption evidence, and candidate figures |

### Trying it before your data is ready

```bash
python scripts/make_synthetic_data.py --n-final 180
```

This writes a fake 219-row export to `data/raw/` that screens down to 180, so you
can watch the whole workflow run and see the shape of every output. Delete it before
you work with your real data so the two can never be confused.

---

## Part 4 — What the scripts deliberately leave to you

They stop short of the inferential analysis, because the model has to match the
data analysis plan you agreed with your supervisor, and because your DAP feedback
should drive it. `config/study.yaml` records which model you intend (`correlation`,
`regression`, `mediation`, `moderation`) so the right assumption tests run, and
`assumptions.md` prints a basic OLS fit as a sanity check — but treat that as
scaffolding, not as your reported analysis.

For mediation or moderation specifically, you will most likely want PROCESS (in
SPSS or R) or `statsmodels` with bootstrapped indirect effects. Confirm the approach
with your supervisor in one of your two supervision sessions rather than picking one
here.

## A caution about statistical choices

These scripts implement common, defensible conventions: `±3.29` for univariate
outliers, Mahalanobis distance at *p* < .001 for multivariate outliers, 20% as the
prorating threshold, VIF < 10 for multicollinearity. They are conventions, not
rules, and your unit materials or supervisor may specify different ones. Where they
differ, follow your unit materials and change the thresholds in the config or the
script.
