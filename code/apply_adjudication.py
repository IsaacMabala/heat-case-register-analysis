"""Apply the completed coding adjudication to the anonymised datasets and regenerate every dependent result.

Usage
-----
python apply_adjudication.py --audit restricted/coding_audit_ADJUDICATED.csv [restricted/coding_audit_as_recorded_ADJUDICATED.csv] \
                             --datasets datasets/cases.csv [datasets/cases_as_recorded.csv] \
                             [--specialist restricted/specialist_blinded_recoding.csv --key restricted/specialist_key_ANALYST_ONLY.csv] \
                             [--out results_adjudicated] [--strict]

What it does
------------
1. Reads each completed audit (one row per automated match) and applies the decision in `adjudication_decision`:
   accept  -> the provisional category stands;
   reject  -> the match is discarded;
   recode  -> the match is moved to `final_category` (must be one of the twelve classes);
   blank   -> pending: the provisional category is retained and counted (the run is refused with --strict).
2. Collapses duplicate phrase matches to one case-source-category result and rebuilds every C::<class> and I::<class> flag
   in the dataset from the adjudicated matches (a class is present only if at least one accepted or recoded match lands on it).
3. Writes cases_adjudicated.csv (and cases_as_recorded_adjudicated.csv when the second audit and dataset are given), then re-runs the
   public analysis (all tables and summaries, and the as-recorded comparison when both sets are given) into --out
   with the coded-statement tables labelled "adjudicated", and records adjudication_version.json with the SHA-256 of each
   audit file and each adjudicated dataset and the decision counts.
4. If a returned specialist file and the analyst key are supplied, computes agreement between the specialist codes and the
   automated codes per field and class (positive agreement, negative agreement, confirmation rate and Cohen's kappa) into
   T_validation_agreement.csv. Agreement statistics describe the enriched validation sample, not the corpus.
   (No specialist re-coding was performed for revision 3.3; the adjudication was done by a single reviewer.)

adjudicate_dataset() and validation_agreement() can also be imported (the Colab workbook does this in register mode).
"""
import argparse, hashlib, json, os, sys, datetime as dt
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)


def sha(path): return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def adjudicate_dataset(audit_path, dataset_path, out_path, rules, strict=False):
    """Rebuild the C::/I:: flags of one anonymised dataset from a completed audit; returns the decision counts."""
    tag = os.path.basename(dataset_path)
    au = pd.read_csv(audit_path, dtype=str).fillna('')
    au['adjudication_decision'] = au['adjudication_decision'].str.strip().str.lower()
    counts = au['adjudication_decision'].replace('', 'pending').value_counts().to_dict()
    bad = au[~au['adjudication_decision'].isin(['accept', 'reject', 'recode', ''])]
    if len(bad): raise SystemExit(f'{tag}: unrecognised decisions: {sorted(bad.adjudication_decision.unique())}')
    if strict and counts.get('pending', 0): raise SystemExit(f'{tag}: {counts["pending"]} matches still pending adjudication (run without --strict to keep them provisional)')
    rec = au[au.adjudication_decision == 'recode']; badcat = rec[~rec.final_category.isin(rules)]
    if len(badcat): raise SystemExit(f'{tag}: recode rows with an unknown final_category: {sorted(badcat.final_category.unique())}')
    keep = au[au.adjudication_decision.isin(['accept', '']).values].assign(category=lambda d: d.provisional_category)
    keep = pd.concat([keep, rec.assign(category=lambda d: d.final_category)], ignore_index=True)
    keep = keep[['case_id', 'source_field', 'category']].drop_duplicates()   # collapse duplicate phrase matches
    df = pd.read_csv(dataset_path)
    for label in rules:
        for src, col in (('complaint', 'C'), ('investigation', 'I')):
            ids = set(keep[(keep.source_field == src) & (keep.category == label)].case_id)
            df[f'{col}::{label}'] = df.case_id.isin(ids)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    df.to_csv(out_path, index=False)
    return counts


def validation_agreement(specialist_path, key_path, rules, out_csv):
    sp = pd.read_csv(specialist_path, dtype=str).fillna(''); key = pd.read_csv(key_path, dtype=str).fillna('')
    m = sp.merge(key, on='blinded_validation_id', how='inner'); rows = []
    split = lambda s: set(x.strip() for x in s.split(';') if x.strip())
    for src, scol, acol in (('complaint', 'specialist_codes_complaint', 'automated_codes_complaint'), ('investigation', 'specialist_codes_investigation', 'automated_codes_investigation')):
        for label in rules:
            s_ = m[scol].map(lambda v: label in split(v)); a_ = m[acol].map(lambda v: label in split(v))
            n = len(m); a11 = int((s_ & a_).sum()); a00 = int((~s_ & ~a_).sum()); a10 = int((~s_ & a_).sum()); a01 = int((s_ & ~a_).sum())
            po = (a11 + a00) / n if n else np.nan; pe = ((a11 + a10) * (a11 + a01) + (a00 + a01) * (a00 + a10)) / (n * n) if n else np.nan
            kappa = (po - pe) / (1 - pe) if n and pe < 1 else np.nan
            rows.append({'source_field': src, 'class': label, 'records': n, 'both': a11, 'automated only': a10, 'specialist only': a01, 'neither': a00,
                         'positive agreement': f'{2 * a11 / (2 * a11 + a10 + a01):.2f}' if (2 * a11 + a10 + a01) else '-', 'negative agreement': f'{2 * a00 / (2 * a00 + a10 + a01):.2f}' if (2 * a00 + a10 + a01) else '-',
                         'confirmation rate of automated codes': f'{a11 / (a11 + a10):.2f}' if (a11 + a10) else '-', 'agreement rate': f'{po:.2f}', 'kappa (within the enriched sample)': f'{kappa:.2f}' if not np.isnan(kappa) else '-'})
    pd.DataFrame(rows).to_csv(out_csv, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audit', nargs='+', required=True, metavar='AUDIT', help='adjudicated audit of the analysis set, then optionally of the register as recorded')
    ap.add_argument('--datasets', nargs='+', required=True, metavar='CSV', help='analysis-set dataset, then optionally the as-recorded dataset')
    ap.add_argument('--specialist', default=None); ap.add_argument('--key', default=None)
    ap.add_argument('--out', default='results_adjudicated'); ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()
    os.environ['RESULTS_DIR'] = args.out; os.environ['CODE_LABEL'] = 'adjudicated'
    import analysis_v4 as a32
    rules = list(a32.RULES.keys())
    os.makedirs(args.out, exist_ok=True)
    version = {'applied': dt.datetime.now().isoformat(timespec='seconds'), 'audits': {}, 'decisions': {}}
    paths = {}
    if len(args.audit) != len(args.datasets) or not 1 <= len(args.audit) <= 2: sys.exit('give one audit and one dataset (analysis set), or two of each (analysis set, then as recorded)')
    pairs = [('main', args.audit[0], args.datasets[0])] + ([('as_recorded', args.audit[1], args.datasets[1])] if len(args.audit) == 2 else [])
    for tag, audit, ds in pairs:
        outpath = os.path.join(args.out, 'datasets', 'cases_adjudicated.csv' if tag == 'main' else f'cases_{tag}_adjudicated.csv')
        counts = adjudicate_dataset(audit, ds, outpath, rules, strict=args.strict)
        version['audits'][tag] = {'file': os.path.basename(audit), 'sha256': sha(audit)}; version['decisions'][tag] = counts; paths[tag] = outpath
        print(f'{tag}: decisions {counts}')
    dfs = {tag: a32.load_dataset(p) for tag, p in paths.items()}
    SM = a32.analyse(dfs['main'], 'main')
    if 'as_recorded' in dfs: SA = a32.analyse(dfs['as_recorded'], 'as_recorded'); a32.as_recorded_comparison(SM, SA)
    version['results_dir'] = os.path.basename(os.path.normpath(args.out)); version['datasets'] = {tag: {'file': os.path.basename(p), 'sha256': sha(p)} for tag, p in paths.items()}
    json.dump(version, open(os.path.join(args.out, 'adjudication_version.json'), 'w'), indent=1)
    print('adjudicated results written to', args.out)
    if args.specialist and args.key:
        validation_agreement(args.specialist, args.key, rules, os.path.join(args.out, 'T_validation_agreement.csv')); print('validation agreement written')


if __name__ == '__main__':
    main()
