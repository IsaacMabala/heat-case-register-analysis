# Heat-case register analysis — code, results and supplementary material

Companion repository for the paper

> Mochubele, M. and Mabala, M.I. *Heat-case register analysis to inform continuous risk assessment and hybrid occupational hygiene and ventilation monitoring in a deep-level gold-mining complex.* Submitted to the *Journal of the Southern African Institute of Mining and Metallurgy*.

The paper reads the heat-case register of a two-shaft deep-level gold-mining complex (179 rows over 23 months, cleaned to an analysis set of 178 cases) for what it can and cannot tell a practitioner: where the case-linked wet-bulb, dry-bulb and air-velocity readings sat relative to the statutory limits, the regulator's reporting bands and provisional air-velocity screens; which occupations, shifts, weekdays, levels and raise lines carried the cases; and what the investigations, the complaints and the worker-context fields recorded. Every finding in the paper is reported with its estimate, its precision and its practical meaning. This repository holds everything behind those findings: the analysis and figure code, every result table, the full table of statistical tests, the supplementary figures and tables that did not fit the journal's page limit, and plain-language notes on the statistical tools for readers without a statistical background.

The mining complex is not named. The two shafts are reported as Shaft A and Shaft B, raise lines and sections are coded in order of case count (A126-R1 is the raise line with the most cases on the 126 level of Shaft A), and no narrative text, register row numbers or personal information appear anywhere in this repository.

## Where to find what the paper refers to

| In the paper | File here |
|---|---|
| Table I — the analysis set after cleaning | `results/main/T01_cohort.csv`, `T01b_flagged_velocity_readings.csv`, `T01c_date_and_duplicate_flags.csv` |
| Figure 1 — wet-bulb and velocity at the case-linked readings | `figures/Figure_1_wetbulb_velocity_state.png`; data `results/main/T03_band_by_velocity.csv`, `T03b_environment_state.csv`, `T03c_statutory_limit_records.csv` |
| Table II — cases by occupation group | `results/main/T05_occupation.csv` |
| Figure 2 — cases per month and the permutation tests | `figures/Figure_3_monthly_cases_by_shaft.png`; data `results/main/T06c_monthly.csv`, `T08b_permutation_tests.csv` |
| Table III — same-level short-window concentrations | `results/main/T08_cluster_windows.csv` |
| Figure 3 — coded complaint and investigation statements | `figures/Figure_5_coded_statements.png`; data `results/main/T09_documentary_mentions.csv` |
| Table IV — environmental state × worker-context indicators | `results/main/T11_environment_by_worker_context.csv` (and `T11b_…_1_0_screen.csv` for the 1.0 m/s screen) |
| Table V — principal estimates, meaning and action | compiled from `results/main/T12_statistical_tests.csv` and `summary_main.json` |
| Table VI — information gaps and requirements; Table VII — risk-assessment triggers | derived in the paper; the graded triggers are also drawn in Figure 4 |
| Figure 4 — integration into continuous risk assessment | `figures/Figure_7_CRA_integration.png` |
| Figure 5 — six-layer hybrid monitoring architecture | `figures/Figure_8_hybrid_architecture.png` |
| Figure 6 — historical heat-case evidence dashboard | `figures/Figure_9_historical_dashboard.png` |
| Figure S1 — the weekday profile | `figures/Figure_2_weekday_profile.png`; data `results/main/T06_weekday.csv`, `T06e_poisson_calendar_model.csv`, `T06f_weekday_model_robustness.csv`, `T06g_alcohol_explicit_timing_sensitivity.csv` |
| Figure S2 — raise lines | `figures/Figure_4_raise_line_recurrence.png`; data `results/main/T07b_raise_lines.csv` |
| Figure S3 — worker-context indicators by designation | `figures/Figure_6_worker_context_by_designation.png`; data `results/main/T10_worker_context.csv` |
| Figure S4 — future-state dashboard demonstrator (synthetic data) | `figures/Figure_10_future_state_dashboard_SYNTHETIC.png`; series `figures/Figure_10_synthetic_time_series.csv` |
| Table S1 — every statistical test with its q-value | `results/main/T12_statistical_tests.csv`, reproduced in `supplementary/SUPPLEMENT.md` |
| Table S2 — environmental readings by designation, shaft and shift | `results/main/T02_environment_summary.csv`, reproduced in `supplementary/SUPPLEMENT.md` |
| Note S5 — the constrained machine-learning check | `ml_check/` and `supplementary/SUPPLEMENT.md` |
| The statement in the Methodology that the cleaning changes no conclusion | `results/T14_as_recorded_comparison.csv` (analysis set against the register as recorded) |
| The twelve statement classes, the keyword rules and the adjudication counts | `code/phrase_rules.csv`, `adjudication/` |

The figure files keep the numbering of the analysis code (Figures 1–10); the table above gives the correspondence with the six figures of the paper and the four supplementary figures.

## Reading the statistics without a statistical background

The register holds cases but no worker-hours, so none of the statistics in the paper is a rate or a risk. They answer one question: how much confidence can be placed in a count, a difference or a concentration seen in 178 cases? `supplementary/SUPPLEMENT.md` (Note S6) explains each tool in plain terms — what a Wilson confidence interval tells you about a percentage, what an odds ratio and a Fisher exact test compare, why the Mann–Whitney test and the Hodges–Lehmann shift suit skewed readings such as air velocity, what the Poisson calendar model does and does not adjust for, how the two permutation null models test a cluster of cases, and what a Benjamini–Hochberg q-value protects against — with the reference for each tool for readers who want to go further.

## Reproducing the results

```
pip install -r code/requirements.txt
python code/reproduce.py
```

regenerates every table, the summaries, the comparison with the register as recorded and all ten figures into `results_reproduced/` and `figures_reproduced/`. Full settings (20 000 permutations per null model, 2 000 bootstrap resamples) take about ten minutes; `NPERM=2000 NBOOT=200 python code/reproduce.py` gives a quick check. `TEST_LOG.txt` records the clean-directory test run of the analysis package. The same pipeline is available as a Colab workbook in `notebooks/`.

Reproduction needs the anonymised row-level analysis set (`datasets/cases.csv`, 178 rows; and `cases_as_recorded.csv`, 179 rows, used only for the comparison). **These two files are not in the public repository.** The register contains operational, narrative and health information, and the release of even the anonymised row-level set — and in what form (age bands, month-level dates, coarsened rare combinations, controlled access) — is a decision of the data custodian and the research-ethics office. `datasets/README.md` records the status; the files may be requested from the corresponding author under controlled access. Every result table that the paper relies on is, however, in `results/`, so every statistic and figure can be checked without the row-level data.

## Contents

| Folder | Content |
|---|---|
| `code/` | `analysis_v4.py` (data cleaning, reference values, coding rules, every model and test), `figures_v4.py` (all figures), `apply_adjudication.py`, `reproduce.py`, `requirements.txt`, `data_dictionary.csv` (every column of the analysis set), `phrase_rules.csv` (the twelve statement classes as regular expressions) |
| `results/` | `main/` — every result table and `summary_main.json` for the analysis set (n = 178); `as_recorded/` — the same tables for the register as recorded (n = 179); `T14_as_recorded_comparison.csv`; `README_results.txt` |
| `figures/` | Figures 1–10 of the analysis code at 300 dpi (see the correspondence table above) and the synthetic time series behind Figure 10 |
| `supplementary/` | `SUPPLEMENT.md`: supplementary Figures S1–S4 with their interpretation, Tables S1–S2, Note S5 (machine-learning check), Note S6 (the statistical tools explained), Note S7 (deployment of the hybrid architecture and the two dashboards) |
| `adjudication/` | Counts of the single-reviewer adjudication of the keyword-coded statements (decisions by source and class, recodes, evidence strength) and the procedure; the match-level record is restricted |
| `ml_check/` | Outputs and diagnostics of the constrained machine-learning check |
| `notebooks/` | The pipeline as a Colab workbook (clean, and executed at full settings) |
| `references/` | `references_CSL.json` — the 42 references of the paper in CSL-JSON, importable into Zotero (File → Import) or any CSL-aware manager |
| `datasets/` | Status of the row-level data (not distributed here) |

## Reference values used throughout

Statutory thermal-stress limits: 32.5 °C wet-bulb and 37 °C dry-bulb (Mine Health and Safety Act regulations, regulation 9.2(1) and Schedule 22.9); measurement-system thresholds 25.0 °C wet-bulb and 32.0 °C dry-bulb (regulation 9.2(2)(b)). The regulator's reporting Bands A–D are applied to case-linked spot readings as numerical ranges only. Air velocity has no statutory limit: 0.25 m/s is a non-statutory literature reference for gas dilution, 0.5 m/s the prespecified principal analytical review screen (provisional: no mine code of practice was available to the study) and 1.0 m/s an upper sensitivity screen. "Flagged by the review screen" is a reading that warrants review against the mine's code of practice and the measurement context; it is not a compliance finding.

## Citing

Please cite the paper. The repository itself can be cited with the metadata in `CITATION.cff`. Licence: to be set by the authors before the repository is made public (the authors' working assumption is a permissive licence for the code, such as MIT, and Creative Commons Attribution 4.0 for the result tables and figures).

## Contact

M. Mochubele (corresponding author), School of Mining Engineering, University of the Witwatersrand, Johannesburg — mothusi.mochubele@wits.ac.za. M.I. Mabala — isaac.mabala@wits.ac.za.
