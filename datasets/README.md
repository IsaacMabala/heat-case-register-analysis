# Row-level data (not distributed here)

The analysis code expects two files in this folder: `cases.csv` (the cleaned analysis set, 178 cases, one row per case) and `cases_as_recorded.csv` (the register as recorded, 179 rows, used only for the comparison in `results/T14_as_recorded_comparison.csv`). Both are anonymised (coded shafts, levels, raise lines and sections; no narrative text; no register row numbers; coded-statement flags as adjudicated), and `code/data_dictionary.csv` documents every column.

The heat-case register contains operational, narrative and health information and is not public. The release of the anonymised row-level analysis set — and in what form (age bands, month-level dates, coarsened rare combinations, removal of clinically sensitive fields, controlled access, or aggregate tables only) — is a decision of the data custodian and the research-ethics office, and the files are therefore not in this repository. Researchers may request them from the corresponding author under controlled access. Note that month-level dates or age bands would prevent exact reproduction of the weekday, short-window and age results; controlled access to the exact file preserves reproducibility.

Every result table on which the paper relies is in `results/`, so every statistic and figure of the paper can be checked without the row-level data.

Status: **not released** (update this line when the custodian's decision is recorded).
