# Tural

PSY4414 research project — *The Shield of Creativity: Openness Moderates the
Impact of ESL Status on Workplace Bullying*.

Assessment notes and the analysis pipeline for the quantitative results section,
configured from the PSY4412 pre-registration and ethics application.

> **This repository is public.** Participant data must never be committed to it.
> `.gitignore` blocks `data/`, `output/` and all spreadsheet formats by default.
> See [`data/README.md`](data/README.md).

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. get the data (or drop a manual Qualtrics export into data/raw/)
export QUALTRICS_API_TOKEN='...'
python scripts/fetch_qualtrics.py

# 2. work out which of the ~176 shared-battery columns are yours
python scripts/inspect_export.py        # writes output/codebook.md

# 3. put those column names into the config
$EDITOR config/study.yaml

# 4. screen, score, and build the participant flow
python scripts/prepare_data.py

# 5. descriptives, reliabilities, correlations, assumption tests
python scripts/analyse.py

# 6. H1 (t-test) and H2 (moderation with simple slopes)
python scripts/hypothesis_tests.py
```

No data yet? `python scripts/make_synthetic_data.py --n-final 180` writes a fake
export so you can watch the whole workflow run.

## Layout

| Path | Purpose |
| --- | --- |
| `config/study.yaml` | The one file you edit: column names, scales, reverse items, screening rules, model |
| `scripts/fetch_qualtrics.py` | Downloads responses via the Qualtrics API |
| `scripts/inspect_export.py` | Builds a codebook pairing each column with its question text |
| `scripts/prepare_data.py` | Screening, participant flow, reverse scoring, composites |
| `scripts/analyse.py` | Descriptives, Cronbach's alpha, intercorrelations, assumption tests, figures |
| `scripts/hypothesis_tests.py` | H1 independent samples t-test; H2 hierarchical moderation with simple slopes |
| `scripts/make_synthetic_data.py` | Fake export for testing the pipeline safely |
| `data/` | Local only, git-ignored |
| `output/` | Generated reports and figures, git-ignored |

## Documentation

- [The study and its analysis plan](docs/psy4414/study-analysis-plan.md) — start here; design, hypotheses, and open questions for your supervisor
- [Results section requirements](docs/psy4414/results-section-requirements.md) — consolidated from the rubric, submission guidelines and FAQ
- [Getting your Qualtrics data out, and which data you need](docs/psy4414/qualtrics-export-guide.md)
- [Assessment 2 — Results Section](docs/psy4414/assessment-2-results-section.md)
- [Results section checklist](docs/psy4414/results-section-checklist.md)
- [Assessment 1 — Research Portfolio](docs/psy4414/assessment-1-research-portfolio.md)
- [Seven commonly asked questions](docs/psy4414/faq-seven-questions.md)
- [Walkthrough transcript](docs/psy4414/transcript-assessment-walkthrough.md)
