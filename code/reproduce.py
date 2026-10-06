"""One-command reproduction: regenerates every table, summary and figure of the paper from the anonymised, adjudicated analysis set (and the comparison with the register as recorded).
Usage (from the package root):  python code/reproduce.py
Outputs: results_reproduced/ (tables and summaries for the analysis set in main/, the register as recorded in as_recorded/, and T14_as_recorded_comparison.csv) and figures_reproduced/ (Figures 1-10 and the synthetic time series behind Figure 10).
Set NPERM / NBOOT environment variables to reduce run time for a quick check (defaults 20000 / 2000 reproduce the paper exactly).
Set COVERAGE_START / COVERAGE_END (ISO dates) to extend the daily calendar to the register's administrative coverage once the custodian confirms it."""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
ds = os.path.join(root, 'datasets')
env = dict(os.environ, RESULTS_DIR=os.path.join(root, 'results_reproduced'), FIG_DIR=os.path.join(root, 'figures_reproduced'), DATASET=os.path.join(ds, 'cases.csv'), CODE_LABEL='adjudicated')
subprocess.check_call([sys.executable, os.path.join(here, 'analysis_v4.py'), '--from-dataset', os.path.join(ds, 'cases.csv'), os.path.join(ds, 'cases_as_recorded.csv')], env=env, cwd=root)
subprocess.check_call([sys.executable, os.path.join(here, 'figures_v4.py')], env=env, cwd=root)
print('reproduction complete: results_reproduced/ and figures_reproduced/')
