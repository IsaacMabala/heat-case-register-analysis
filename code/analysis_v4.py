"""Revision 4 analysis for the heat-case register paper: one cleaned analysis set.

Two entry points
----------------
python analysis_v4.py --from-register heat_cases.xlsx          (restricted stage: needs the register and restricted/shaft_map.json;
                                                                writes the anonymised datasets, the restricted crosswalks and audits,
                                                                and then runs the public analysis)
python analysis_v4.py --from-dataset cases.csv [cases_as_recorded.csv]
                                                               (public stage: regenerates every non-restricted table and summary
                                                                from the anonymised analysis set alone; the optional second file
                                                                re-runs the analysis on the register as recorded and writes the
                                                                comparison table T14 that supports the one-sentence statement in
                                                                the paper that no conclusion depends on the cleaning)

Data cleaning (the analysis set, n = 178)
-----------------------------------------
Of the 179 recorded rows, one candidate duplicate (identical age, occupation, shaft, workplace, dates, designation and
screening date) is removed, and four date fields whose recorded value is contradicted by the register's own fields are
corrected by rule: two case dates that lie more than 30 days from the diagnosis date are inferred from the diagnosis
date and the recorded weekday, and two diagnosis dates are read with day and month swapped or with a three-digit year
completed. Every correction is listed with its register row in restricted/T00_inferred_corrections_rows.csv.
Environmental analyses use quality-valid readings only (complete wet-bulb, dry-bulb and velocity without a review flag);
flagged readings are retained in the data and listed. A secondary check includes the 5.1 m/s high-value reading.
The register as recorded (n = 179, no correction) is kept as datasets/cases_as_recorded.csv for the comparison only.

Reference values
----------------
Statutory thermal-stress occupational exposure limits (MHSA regulation 9.2(1), Schedule 22.9(2)(b)(ii)):
wet-bulb 32.5 C, dry-bulb 37 C. DMPR reporting bands (numerical ranges applied here to case-linked readings):
A: WB > 32.5 or DB > 37; B: 29 < WB <= 32.5; C: 27.5 < WB <= 29 (or DB > 32.5 with WB <= 27.5); D: WB <= 27.5 and DB <= 32.5.
Air velocity has no statutory limit; screens: 0.25 m/s (general working-area minimum cited in design literature),
0.5 m/s (prespecified principal analytical review screen, provisional), 1.0 m/s (upper sensitivity screen).
"""
import re, datetime as dt, os, sys, json, warnings
from collections import Counter, OrderedDict
import pandas as pd, numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests
import statsmodels.api as sm
import statsmodels.formula.api as smf
warnings.filterwarnings('ignore')

ROOT = os.environ.get('RESULTS_DIR', 'results_v4')
COVERAGE_START = os.environ.get('COVERAGE_START')  # optional ISO dates to extend the daily calendar to the register's administrative coverage
COVERAGE_END = os.environ.get('COVERAGE_END')
NPERM = int(os.environ.get('NPERM', 20000)); NBOOT = int(os.environ.get('NBOOT', 2000))
SEED = 2026
CODE_LABEL = os.environ.get('CODE_LABEL', 'provisional')  # label attached to the coded-statement tables; apply_adjudication.py sets 'adjudicated'

MONTHS = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
DM = {'MON': 0, 'TUE': 1, 'TUES': 1, 'WED': 2, 'THU': 3, 'THUR': 3, 'THURS': 3, 'FRI': 4, 'FRID': 4, 'SAT': 5, 'SUN': 6}
WK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# ----------------------------------------------------------------------------- coded-statement rules (source-separated)
RULES = OrderedDict([
    ('Ventilation controls absent or substandard', r'VENT(ILATION)? CONTROL|BRATTICE|CURTAIN|VENT DOOR|VENTILATION DOOR|DOORS? (LEFT )?OPEN|DOOR.*(BROKEN|NOT WORKING)|WALL (WAS |BROKEN)|NOT SEALED|SEAL OFF|SHORT ?CIRCUIT|NO CONTROLS INSTALLED|NO VENT CONTROLS|VENTILATION LEAKAGE|POOR VENT(ILATION)?|DECREASED VENTILATION|LACK OF VENTILATION|NO VENTILATION PIPES|AIR TO FACE NOT SUFFICIENT|NO FLOW OF AIR|AIR.*INSUFFICIENT|REDUC(ED|ING) AIR|NO AIR|FIXING VENTILATION'),
    ('Fan not operating, not installed or obstructed', r'FAN[S]? (WAS |WERE |IS |ARE )?(NOT|DOWN|TRIPPING|MALFUNCTION|BROKEN|BURNT|OBSTRUCTED|REMOVED|NOT WORKING|NOT INSTALLED|NOT EXTENDED|NOT OPERATING|NOT FUNCTIONING|NOT EFFECTIVE)|MALFUNCTIONING FAN|FAN MALFUNCTION|NO (COOLING )?FANS?|FANS? DOWN|BURNT OUT FAN|REPLACE.*FAN|FAN OBSTRUCTED|FAN DAMAGE|FAN NOT|FANS?.{0,20}TRIPPING|CHANGING FANS'),
    ('Ventilation column or duct leakage or distance', r'(COLUMN|DUCT|PIPE)S?.*(LEAK|DISTANCE|OVER \d+ ?M|FROM (THE )?FACE)|LEAKAGE[S]? (OVER|PAST|OF|IN|FROM)|EXCESSIVE (VENT(ILATION)? )?(COLUMN )?LEAKAGE|COLUMN LEAKAGE|LEAKING EXCESSIVELY|VENT COLUMN|LEAKAGES? NOT AT 10 ?%'),
    ('Ore or material accumulation obstructing airflow', r'ACCUMULAT|CHOKED|RESTRICT|OBSTRUCT|BLOCKED|TIP COVER|KEPT CLEAR|CONGEST'),
    ('Local cooling equipment (cooling car, in-stope cooler)', r'COOLING CAR|INSTOPE COOLER|IN-STOPE|COOLER|COILS|COOLING PERFOMANCE|COOLING PERFORMANCE|CHILLED WATER COLUMN|COOLING FAN|ATOMI[SZ]ER|OPTIMIZER|COOLING INSTALLATION|COLING CAR'),
    ('Mine-level refrigeration (fridge plant, bulk air cooler, chilled water)', r'FRIDGE|BAC\b|BULK AIR|CHILLED WATER TEMP|REFRIGERAT|HIGH DAM TEMP'),
    ('Water, wet conditions or fissure heat', r'WATER (ON|IN|INTO|CONTROL|PIPES)|EXCESSIVE WATER|STAGNANT|FISSURE|WET\b|SATURATED|HOT WATER|DRAIN|WATER ACCUMULATION'),
    ('Work organisation (staff shortage, overtime, long shift, extra task)', r'SHORTAGE|OVERTIME|13 HOURS|12 HOURS|LONGER|CONTINUOUSLY|EXTRA WORK|WORKING ALONE|NOT HIS NORMAL JOB|SUPPORT WORK|WALK(ING|ED)? (FOR )?LONG|LONG DISTANCE|FATIGUE|BONUS|DIDN.T WANT TO WITHDRAW|MORE THAN \d+ ?H|LABOUR ABSENT'),
    ('Drinking-water shortage', r'NO WATER SU|LACK OF WATER|1 L OF WATER|NO WATER IN THE AREA'),
    ('Complaint not acted on or hazard known', r'NO ACTION TAKEN|KNOWN TO BE HOT|REPORTED SINCE|FOR A MONTH|FOR 3 MONTHS|NOT REPORTED TO SUPERVISORS|THOUGH IT WAS REPORTED|NO INTERVENTION|COMPLAINED.*REPEATEDLY'),
    ('Entry examination, temperature measurement or supervision not done', r'NOT CHECKED ON ENTRY|NO EARLY ENTRY|ENTRY EXAM|NO EQUIPMENT TO CHECK|WHIRLING HYGROMETER|NO SUPERVISION|SUPERVISION NOT|NOT TAKING MEASUREMENTS|CHECK COOLING BEFORE'),
    ('No substandard condition identified', r'NO SUBSTANDARD|NONE OBSERVED|NONE NOTED|NOTHING NOTED|WITHIN THE STANDARD|EVERYTHING WAS NORMAL|NO DEVIATION|WORKING PLACE WAS COOL|^NORMAL$|NO SUB STANDARD|CONDITIONS (ARE )?GOOD'),
])
OPERATIONAL = list(RULES.keys())[:7]
NOT_DONE = r'NOT DONE|SEC 11\.5|^N/?A$|REFERRED TO PD449$'
STATES = ['Band B or C; velocity >=0.5 m/s', 'Band B or C; velocity 0.25-<0.5 m/s', 'Band B or C; velocity <0.25 m/s', 'Band A or at its limit', 'Band D (below hot threshold)', 'Not assessable']
WCI = 'Recorded worker-context indicator'; NOWCI = 'No recorded worker-context indicator'
FLAG = 'Flagged by the review screen (above or at the statutory limit, or velocity <0.5 m/s)'; NOFLAG = 'Within the review screen (Band B/C with velocity >=0.5 m/s, or Band D)'

SPECIALIST_INSTRUCTIONS = """BLINDED RE-CODING OF HEAT-CASE NARRATIVES (validation sample, 60 records)

You are asked to code two short texts per record: the employee's complaint and the heat-investigation statement. Code each field separately.
For each field, list every class below that the text documents; leave the cell blank if none applies. Use the class names exactly as written, separated by semicolons.
Code only what the text states. A control that is merely mentioned (for example a cooling car that is named without being reported as faulty) is NOT a deficiency. A statement that a control was functioning or that no substandard condition was found is coded as 'No substandard condition identified'.

Classes:
1. Ventilation controls absent or substandard - brattices, curtains, vent doors, walls or seals absent, open, broken, leaking or short-circuiting; insufficient or no air reported at the face.
2. Fan not operating, not installed or obstructed - a fan reported as down, tripping, burnt, removed, obstructed, not installed, not extended or not effective.
3. Ventilation column or duct leakage or distance - columns, ducts or pipes reported as leaking, damaged or too far from the face.
4. Ore or material accumulation obstructing airflow - ore, rock or material reported as choking, blocking, restricting or obstructing the airway, gully or raise.
5. Local cooling equipment (cooling car, in-stope cooler) - a cooling car, in-stope cooler, coils or cooling fan reported as absent, off or under-performing.
6. Mine-level refrigeration (fridge plant, bulk air cooler, chilled water) - a fridge plant, bulk air cooler or chilled-water supply reported as off, tripped or under-performing.
7. Water, wet conditions or fissure heat - excessive, stagnant or hot water, wet or saturated conditions, fissure water or heat, drainage problems.
8. Work organisation (staff shortage, overtime, long shift, extra task) - shortage of staff, overtime, 12- or 13-hour shifts, continuous work, extra or unfamiliar tasks, long walking distances, fatigue, bonus pressure.
9. Drinking-water shortage - no or insufficient drinking water reported.
10. Complaint not acted on or hazard known - the area was known or reported to be hot before, a complaint was made or repeated without action, or the hazard was known and not reported.
11. Entry examination, temperature measurement or supervision not done - no or late entry examination, no temperature check or instrument, or supervision absent or not measuring.
12. No substandard condition identified - the investigation states that nothing substandard, abnormal or deviating was found.

Do not consult the mine register, the case files or any other person while coding. Return the file with the three specialist columns completed; the notes column is for anything that does not fit the classes.
"""

def code_text(text):
    return {label: (lambda m: m.group(0) if m else None)(re.search(pat, text)) for label, pat in RULES.items()}

# ============================================================================= STAGE 1: restricted build from the register
def parse_date(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    if isinstance(v, dt.datetime): return v.date()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', str(v).strip())
    if not m or len(m.group(3)) == 3: return None
    d_, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3)); y = y + 2000 if y < 100 else y
    try: return dt.date(y, mo, d_)
    except Exception: return None
def num(v):
    if v is None: return np.nan
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).strip())
    except Exception: return np.nan
def norm(v): return str(v).strip().upper() if v is not None and not (isinstance(v, float) and np.isnan(v)) else ''

def load_register(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True); ws = wb['Sheet1']
    hdr = [c.value for c in ws[1]]; recs = []
    for r in ws.iter_rows(min_row=2, max_row=ws.max_row):
        vals = [c.value for c in r]
        if all(v is None or str(v).strip() == '' for v in vals): continue
        d = {(hdr[i].strip() if hdr[i] else f'col{i}'): vals[i] for i in range(len(vals))}; d['xl_row'] = r[0].row; recs.append(d)
    raw = pd.DataFrame(recs); assert len(raw) == 179; return raw

def build(RAW, SHAFT, mode):
    df = RAW.copy(); DUPKEY = ['Age', 'Occupation', 'Shaft', 'Workplace', 'DOA', 'Date Final diagnosis', 'Body Cramps', 'Heat Cramps', 'Last HTS date']
    df['doa_raw'] = df['DOA'].map(parse_date); df['dx_raw'] = df['Date Final diagnosis'].map(parse_date)
    df['dup_candidate'] = df.duplicated(DUPKEY, keep=False); log = []
    df['dx'] = df['dx_raw']; df['dx_flag'] = ''
    for i, r in df.iterrows():
        s = str(r['Date Final diagnosis']).strip()
        if r['dx'] is None and re.match(r'^\d{1,2}/\d{1,2}/\d{3}$', s):
            df.at[i, 'dx_flag'] = 'diagnosis date unparseable (three-digit year)'
            if mode == 'clean' and r['doa_raw']:
                d_, mo, _ = s.split('/'); df.at[i, 'dx'] = dt.date(r['doa_raw'].year, int(mo), int(d_)); log.append((int(r.xl_row), 'Diagnosis date', f'"{s}" read as {df.at[i, "dx"]}'))
        if isinstance(r['Date Final diagnosis'], dt.datetime) and r['doa_raw'] is not None:
            dd = r['Date Final diagnosis']; alt = dt.date(dd.year, dd.day, dd.month) if dd.day <= 12 else None
            if alt is not None and 0 <= (alt - r['doa_raw']).days <= 7 and (dd.date() - r['doa_raw']).days > 20:
                df.at[i, 'dx_flag'] = 'diagnosis date possibly month/day swapped'
                if mode == 'clean': df.at[i, 'dx'] = alt; log.append((int(r.xl_row), 'Diagnosis date', f'{dd.date()} read as {alt}'))
    df['doa'] = df['doa_raw']; df['doa_flag'] = ''
    for i, r in df.iterrows():
        if r['doa'] is None or r['dx'] is None: continue
        lag = (r['dx'] - r['doa']).days
        if lag < 0 or lag > 30:
            df.at[i, 'doa_flag'] = f'case date {lag} days from diagnosis date; internally inconsistent'
            if mode == 'clean':
                wd = DM.get(norm(r['DAY'])); cand = None
                for back in range(0, 8):
                    c = r['dx'] - dt.timedelta(days=back)
                    if wd is None or c.weekday() == wd: cand = c; break
                if cand: df.at[i, 'doa'] = cand; log.append((int(r.xl_row), 'Case date', f'{r["doa_raw"]} inferred as {cand} from diagnosis date, recorded weekday and adjacent rows'))
        wd = DM.get(norm(r['DAY']))
        if wd is not None and r['doa'] and r['doa'].weekday() != wd and not df.at[i, 'doa_flag']: df.at[i, 'doa_flag'] = 'recorded weekday disagrees with case date'
    if mode == 'clean':
        for _, r in df[df.duplicated(DUPKEY, keep='first')].iterrows(): log.append((int(r.xl_row), 'Candidate duplicate', 'removed from the analysis set'))
        df = df[~df.duplicated(DUPKEY, keep='first')].copy()
    df['wb'] = df['Wet bulb'].map(num); df['db'] = df['Dry bulb'].map(num); df['vel'] = df['Velocity'].map(num)
    def qc(r):
        if np.isnan(r.vel): return ''
        if not np.isnan(r.db) and r.vel == r.db and r.vel > 5: return 'copied-value logic failure (velocity equals the dry-bulb entry)'
        if r.vel > 10: return 'extreme high-value review (above 10 m/s)'
        if r.vel > 5: return 'high-value review (above 5 m/s)'
        if not np.isnan(r.wb) and not np.isnan(r.db) and r.wb > r.db: return 'wet-bulb above dry-bulb'
        return ''
    df['qc_flag'] = df.apply(qc, axis=1)
    df['triplet'] = df[['wb', 'db', 'vel']].notna().all(axis=1); df['complete'] = df['triplet'] & (df['qc_flag'] == '')
    df['year'] = df['doa'].map(lambda d: d.year); df['month'] = df['doa'].map(lambda d: d.strftime('%Y-%m')); df['weekday'] = df['doa'].map(lambda d: d.strftime('%A'))
    df['dx_lag_days'] = [(a - b).days if a and b else np.nan for a, b in zip(df['dx'], df['doa'])]
    df['season'] = df['doa'].map(lambda d: 'Summer' if d.month in (12, 1, 2) else 'Autumn' if d.month in (3, 4, 5) else 'Winter' if d.month in (6, 7, 8) else 'Spring')
    df['designation'] = df.apply(lambda r: 'Heat stroke' if norm(r['Body Cramps']) == 'HEAT STROKE' else 'Heat cramps' if norm(r['Heat Cramps']) else 'Body cramps' if norm(r['Body Cramps']) else 'Unclassified', axis=1)
    df['shaft'] = df['Shaft'].map(lambda v: SHAFT.get(norm(v), 'Unknown'))
    df['employment'] = df['Perm/Contractor'].map(lambda v: 'Contractor' if 'CONTR' in norm(v) else 'Permanent' if 'PERM' in norm(v) else 'Unknown')
    df['shift'] = df['Shift'].map(lambda v: 'Day' if norm(v) == 'DAY' else 'Night' if norm(v) == 'NIGHT' else 'Not recorded')
    df['workplace'] = df['Workplace'].map(lambda v: re.sub(r'\s+', ' ', norm(v))); df['section_raw'] = df['Section'].map(norm); df['workplace_recorded'] = df['workplace'] != ''
    df['level'] = df['workplace'].map(lambda w: (lambda m: m.group(1) if m and m.group(1) != '999' else None)(re.match(r'^(\d{3})\b', w)))
    df['raise'] = df['workplace'].map(lambda w: (lambda m: m.group(2) if m else None)(re.match(r'^(\d{3})\s*[EW]?\s*(?:MP|MT)?\s*(?:VCR|CLR|CL)?\s*[-/]?\s*(\d{2})\b', w)))
    df['raise_key'] = [f'{s}-{l}-{r}' if isinstance(l, str) and isinstance(r, str) else None for s, l, r in zip(df['shaft'], df['level'], df['raise'])]
    def occ_group(v):
        s = norm(v)
        if re.search(r'SCRAPER|WINCH|SWO', s): return 'Scraping and winching'
        if re.search(r'DEV|RAISE|HPE|DRILL RIG|DROPRAISE', s): return 'Development and raise work'
        if re.search(r'BLAST', s): return 'Blasting and charging'
        if re.search(r'LOCO|LOADER|CLEANER', s): return 'Transport, loading and cleaning'
        if re.search(r'ENGIN|FITTER|MES & LACING', s): return 'Engineering and services'
        if re.search(r'SHIFT BOSS|OVERSEER', s): return 'Supervision'
        if re.search(r'MINING TEAM|STOPE|RDO|STOPER', s): return 'Stoping and production'
        return 'Other or unclear'
    df['occ_raw'] = df['Occupation'].map(norm); df['occ_group'] = df['Occupation'].map(occ_group); df['occ_generic'] = df['occ_raw'].eq('MINING TEAM')
    df['complaint'] = df['EMPLOYEE COMPLAINTS/FACTORS'].map(norm); df['investigation'] = df['HEAT INVESTIGATION'].map(norm)
    df['complaint_present'] = ~df['complaint'].isin(['', 'N/A', 'NA']); df['inv_not_done'] = df['investigation'].map(lambda t: bool(re.search(NOT_DONE, t)) or t == '')
    df['complaint_words'] = df['complaint'].map(lambda t: len(t.split())); df['investigation_words'] = df['investigation'].map(lambda t: len(t.split()))
    cc = df['complaint'].map(code_text); ci = df['investigation'].map(code_text)
    for label in RULES:
        df[f'C::{label}'] = cc.map(lambda d: d[label] is not None); df[f'I::{label}'] = ci.map(lambda d: d[label] is not None)
        df[f'C_phrase::{label}'] = cc.map(lambda d: d[label]); df[f'I_phrase::{label}'] = ci.map(lambda d: d[label])
    NEG = ('NONE', 'NIL', 'NIL RECENT', 'NO', 'NEVER', 'NONE REPORTED', 'NONE RECENTLY', 'NIL NOTED')
    df['prev_episode'] = df['Previous Episodes'].map(lambda v: 'Not recorded' if norm(v) == '' else 'None recorded' if norm(v) in NEG else 'Previous episode recorded')
    df['med_condition'] = df['MEDICAL CONDITIONS'].map(lambda v: 'Yes' if norm(v).startswith('YES') else 'No' if norm(v) in ('NO', 'NONE', 'NIL') else 'Not recorded')
    def med_control(r):
        if r['med_condition'] != 'Yes': return 'No condition recorded'
        s = norm(r['Control of medical conditions'])
        if s in ('CONTROLLED', 'GOOD', 'ACCEPTABLE', 'YES', 'IMPROVING'): return 'Controlled or acceptable'
        if s in ('PARTIALLY', 'POOR', 'DEFAULTED', 'NOT CONTROLLED', 'NO'): return 'Poorly or partly controlled'
        return 'Control not known'
    df['med_control'] = df.apply(med_control, axis=1)
    df['acute_illness'] = df['Acute illness at time of the cramps'].map(lambda v: 'Yes or possible' if norm(v) in ('YES', 'POSSIBLE', 'MILD ILLNESS') else 'No' if norm(v) in ('NO', 'NIL', 'NONE') else 'Not recorded')
    def alcohol(r):
        s = norm(r['RECENT ALCOHOL USE'])
        if s in ('', 'NOT KNOWN'): return 'Not recorded'
        if s in ('SOBER HABITS', 'NO', 'NONE', 'NIL', 'NIL RECENT', 'DENIES', 'NO RECENT ALCOHOL INTAKE'): return 'Sober habits or no recent use'
        m = re.match(r'^(\d{2}) ([A-Z]{3})$', s)
        if m and r['doa']:
            try:
                d_ = dt.date(r['doa'].year, MONTHS[m.group(2)], int(m.group(1))); return 'Within 48 h or affirmed' if 0 <= (r['doa'] - d_).days <= 2 else 'More than 48 h before'
            except Exception: pass
        if re.search(r'>\s*48|>\s*72|72 ?H|5 DAYS|NOT IN THE LAST 48|3 DAYS', s): return 'More than 48 h before'
        if re.search(r'<\s*48|WITHIN 48|48 ?HRS AGO|48 HOURS PRIOR|DAY BEFORE|SATURDAY|WEEKEND|^YES$|^POSSIBLE$|LESS THA', s): return 'Within 48 h or affirmed'
        return 'Not recorded'
    df['alcohol'] = df.apply(alcohol, axis=1)
    def alcohol_timing(r):
        if r['alcohol'] != 'Within 48 h or affirmed': return ''
        s = norm(r['RECENT ALCOHOL USE'])
        return 'affirmed without timing' if re.search(r'^YES$|^POSSIBLE$', s) else 'explicit timing'
    df['alcohol_timing'] = df.apply(alcohol_timing, axis=1)
    def parse_hts(v):
        if v is None or (isinstance(v, float) and np.isnan(v)): return None, None
        if isinstance(v, dt.datetime): return (v.year, v.month), 'day'
        s = norm(v).replace('?', '')
        m = re.match(r'^(?:\d{1,2}\s+)?([A-Z]+)\s+(\d{2,4})$', s)
        if m and m.group(1)[:3] in MONTHS:
            y = int(m.group(2)); y = y + 2000 if y < 100 else y; return (y, MONTHS[m.group(1)[:3]]), 'month'
        m = re.match(r'^(\d{1,2})/(\d{4})$', s)
        if m: return (int(m.group(2)), int(m.group(1))), 'month'
        m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', s)
        if m:
            y = int(m.group(3)); y = y + 2000 if y < 100 else y; return (y, int(m.group(2))), 'day'
        m = re.match(r'^(\d{4})$', s)
        if m: return (int(m.group(1)), 6), 'year'
        return None, 'unparsed'
    hts = df['Last HTS date'].map(parse_hts)
    df['hts_precision'] = hts.map(lambda t: t[1] if t[1] else 'missing')
    df['hts_months'] = [((r['doa'].year - h[0][0]) * 12 + (r['doa'].month - h[0][1])) if (h[0] and r['doa']) else np.nan for h, (_, r) in zip(hts, df.iterrows())]
    return df, log

DATASET_COLS = ['case_id', 'doa', 'dx', 'dx_lag_days', 'year', 'month', 'season', 'weekday', 'designation', 'shaft', 'level', 'raise_code', 'section_code', 'employment', 'shift', 'occ_group', 'occ_generic', 'Age', 'wb', 'db', 'vel', 'qc_flag', 'triplet', 'complete',
                'prev_episode', 'med_condition', 'med_control', 'acute_illness', 'alcohol', 'alcohol_timing', 'hts_months', 'hts_precision', 'workplace_recorded', 'complaint_present', 'complaint_words', 'investigation_words', 'inv_not_done', 'dup_candidate', 'doa_flag', 'dx_flag'] + [f'C::{l}' for l in RULES] + [f'I::{l}' for l in RULES]

def stage1(register_path):
    RAW = load_register(register_path); SHAFT = json.load(open('restricted/shaft_map.json'))
    P, plog = build(RAW, SHAFT, 'as_recorded'); Cn, clog = build(RAW, SHAFT, 'clean')
    rk_counts = Counter(k for k in P['raise_key'] if isinstance(k, str)); raise_code = {}
    for s in ('A', 'B'):
        for lvl in sorted(set(l for l, ss in zip(P['level'], P['shaft']) if isinstance(l, str) and ss == s)):
            keys = [k for k in rk_counts if k.startswith(f'{s}-{lvl}-')]
            for n, k in enumerate(sorted(keys, key=lambda k: (-rk_counts[k], k)), start=1): raise_code[k] = f'{s}{lvl}-R{n}'
    sec_counts = Counter(s for s in P['section_raw'] if s); section_code = {s: f'S{n:02d}' for n, s in enumerate(sorted(sec_counts, key=lambda s: (-sec_counts[s], s)), start=1)}
    cid = {r: f'C{i + 1:03d}' for i, r in enumerate(sorted(P.xl_row))}
    RES = f'{ROOT}/restricted'; os.makedirs(RES, exist_ok=True); os.makedirs(f'{ROOT}/datasets', exist_ok=True)
    pd.DataFrame([(k, v, rk_counts[k]) for k, v in raise_code.items()], columns=['raise_key', 'code', 'cases']).to_csv(f'{RES}/raise_crosswalk.csv', index=False)
    pd.DataFrame([(k, v, sec_counts[k]) for k, v in section_code.items()], columns=['section', 'code', 'cases']).to_csv(f'{RES}/section_crosswalk.csv', index=False)
    pd.DataFrame({'case_id': [cid[r] for r in sorted(cid)], 'register_row': sorted(cid)}).to_csv(f'{RES}/case_id_to_register_row.csv', index=False)
    pd.DataFrame(clog, columns=['register_row', 'field', 'inferred_correction']).to_csv(f'{RES}/T00_inferred_corrections_rows.csv', index=False)
    out = {}
    for D, tag in ((Cn, 'main'), (P, 'as_recorded')):
        sfx = '' if tag == 'main' else f'_{tag}'
        D['raise_code'] = D['raise_key'].map(lambda k: raise_code.get(k) if isinstance(k, str) else None); D['section_code'] = D['section_raw'].map(lambda s: section_code.get(s) if s else None); D['case_id'] = D['xl_row'].map(cid)
        D[(D.doa_flag != '') | (D.dx_flag != '') | D.dup_candidate][['case_id', 'xl_row', 'DOA', 'Date Final diagnosis', 'DAY', 'doa_flag', 'dx_flag', 'dup_candidate']].to_csv(f'{RES}/T01c_date_and_duplicate_flags_raw{sfx}.csv', index=False)
        # coding audit: one row per actual match, adjudication fields blank until reviewed
        audit = []
        for _, r in D.iterrows():
            for label in RULES:
                for src in ('C', 'I'):
                    ph = r[f'{src}_phrase::{label}']
                    if isinstance(ph, str) and ph: audit.append({'case_id': r.case_id, 'register_row': int(r.xl_row), 'source_field': 'complaint' if src == 'C' else 'investigation', 'matched_phrase': ph, 'provisional_category': label, 'source_text': r['complaint'] if src == 'C' else r['investigation'],
                                         'adjudication_decision': '', 'final_category': '', 'evidence_strength': '', 'reason_note': '', 'adjudicator': '', 'date': ''})
        pd.DataFrame(audit).to_csv(f'{RES}/coding_audit{sfx}.csv', index=False)
        D[DATASET_COLS].to_csv(f'{ROOT}/datasets/cases{sfx}.csv', index=False); out[tag] = D
    # validation sample design (restricted: contains narratives)
    P_ = out['as_recorded']; rng = np.random.default_rng(SEED)
    inv_neg = P_[(~P_.inv_not_done) & (P_.investigation_words >= 5) & ~P_[[f'I::{l}' for l in OPERATIONAL]].any(axis=1)]
    comp_neg = P_[P_.complaint_present & (P_.complaint_words >= 5) & ~P_[[f'C::{l}' for l in RULES]].any(axis=1)]
    comp_neg_s = comp_neg.sample(n=min(30, len(comp_neg)), random_state=SEED)
    pos = P_[P_[[f'C::{l}' for l in RULES] + [f'I::{l}' for l in RULES]].any(axis=1)]
    # specialist subsample: 30 positive records stratified over classes (at least 2 per class where available), 15 investigation negatives, 15 complaint negatives
    chosen = []
    for label in RULES:
        cand = pos[(pos[f'I::{label}'] | pos[f'C::{label}']) & ~pos.case_id.isin(chosen)]
        for c in cand.sample(n=min(2, len(cand)), random_state=SEED).case_id: chosen.append(c)
    rest = pos[~pos.case_id.isin(chosen)]; chosen += list(rest.sample(n=max(0, 30 - len(chosen)), random_state=SEED).case_id)
    n_inv = min(12, len(inv_neg)); spec = list(chosen) + list(inv_neg.sample(n=n_inv, random_state=SEED).case_id); spec += list(comp_neg_s[~comp_neg_s.case_id.isin(spec)].sample(n=min(60 - len(set(spec)), int((~comp_neg_s.case_id.isin(spec)).sum())), random_state=SEED).case_id)
    rows = []
    for _, r in P_.iterrows():
        tier = []
        if r.case_id in set(pos.case_id): tier.append('author: all matches (census)')
        if r.case_id in set(inv_neg.case_id): tier.append('author: investigation-text apparent negatives (census)')
        if r.case_id in set(comp_neg_s.case_id): tier.append('author: complaint-text apparent negatives (random 30)')
        if r.case_id in set(spec): tier.append('specialist blinded re-coding (60 records)')
        if tier: rows.append({'case_id': r.case_id, 'register_row': int(r.xl_row), 'tiers': '; '.join(tier), 'complaint_text': r['complaint'], 'investigation_text': r['investigation'],
                              'automated_codes_complaint': '; '.join(l for l in RULES if r[f'C::{l}']), 'automated_codes_investigation': '; '.join(l for l in RULES if r[f'I::{l}'])})
    design = pd.DataFrame(rows); design.to_csv(f'{RES}/validation_sample_design_AUTHOR.csv', index=False)
    # blinded specialist file (no identifiers, tiers, automated codes or outcomes) and the analyst-only key
    sp = design[design.tiers.str.contains('specialist')].sample(frac=1.0, random_state=SEED + 7).reset_index(drop=True)
    sp['blinded_validation_id'] = [f'V{i + 1:03d}' for i in range(len(sp))]
    sp[['blinded_validation_id', 'complaint_text', 'investigation_text']].assign(specialist_codes_complaint='', specialist_codes_investigation='', specialist_notes='').to_csv(f'{RES}/specialist_blinded_recoding.csv', index=False)
    sp[['blinded_validation_id', 'case_id', 'register_row', 'tiers', 'automated_codes_complaint', 'automated_codes_investigation']].rename(columns={'tiers': 'sampling_tier'}).to_csv(f'{RES}/specialist_key_ANALYST_ONLY.csv', index=False)
    open(f'{RES}/specialist_instructions.txt', 'w').write(SPECIALIST_INSTRUCTIONS)
    json.dump({'matches_total': int(len(pd.read_csv(f"{RES}/coding_audit_as_recorded.csv"))), 'records_with_any_match': int(len(pos)), 'investigation_apparent_negatives_census': int(len(inv_neg)), 'complaint_apparent_negatives_pool': int(len(comp_neg)), 'complaint_apparent_negatives_sampled': int(len(comp_neg_s)), 'specialist_subsample': int(len(set(spec)))}, open(f'{RES}/validation_sample_summary.json', 'w'), indent=1)
    return out

# ============================================================================= STAGE 2: public analysis from the anonymised datasets
def load_dataset(path):
    df = pd.read_csv(path)
    df['doa'] = pd.to_datetime(df.doa).dt.date; df['dx'] = pd.to_datetime(df.dx, errors='coerce').dt.date
    df['level'] = df.level.map(lambda v: None if pd.isna(v) else str(int(v)) if float(v).is_integer() else str(v))
    for c in ['triplet', 'complete', 'occ_generic', 'workplace_recorded', 'complaint_present', 'inv_not_done', 'dup_candidate'] + [f'C::{l}' for l in RULES] + [f'I::{l}' for l in RULES]: df[c] = df[c].astype(bool)
    for c in ['qc_flag', 'doa_flag', 'dx_flag', 'raise_code', 'section_code']: df[c] = df[c].where(df[c].notna(), None)
    df['alcohol_timing'] = df['alcohol_timing'].map(lambda v: v if isinstance(v, str) else '') if 'alcohol_timing' in df.columns else ''
    df['qc_flag'] = df['qc_flag'].map(lambda v: v if isinstance(v, str) else ''); df['doa_flag'] = df['doa_flag'].map(lambda v: v if isinstance(v, str) else ''); df['dx_flag'] = df['dx_flag'].map(lambda v: v if isinstance(v, str) else '')
    return derive(df)

def derive(df):
    """Derived classifications that depend only on dataset columns (recomputed here so the public script is self-contained)."""
    def band(r):
        if not r.complete: return 'Not assessable'
        if r.wb > 32.5 or r.db > 37.0: return 'Band A'
        if r.wb > 29.0: return 'Band B'
        if r.wb > 27.5 or r.db > 32.5: return 'Band C'
        return 'Band D'
    df['band'] = df.apply(band, axis=1)
    df['at_band_a_limit'] = df.complete & ((df.wb == 32.5) | (df.db == 37.0)) & (df.band != 'Band A')
    def state(r):
        if not r.complete: return 'Not assessable'
        if r.band == 'Band A' or r.at_band_a_limit: return 'Band A or at its limit'
        if r.band == 'Band D': return 'Band D (below hot threshold)'
        if r.vel < 0.25: return 'Band B or C; velocity <0.25 m/s'
        if r.vel < 0.5: return 'Band B or C; velocity 0.25-<0.5 m/s'
        return 'Band B or C; velocity >=0.5 m/s'
    df['env_state'] = df.apply(state, axis=1)
    df['review_flag'] = df.env_state.isin(['Band A or at its limit', 'Band B or C; velocity <0.25 m/s', 'Band B or C; velocity 0.25-<0.5 m/s'])
    df['review_flag_10'] = df.complete & (df.env_state.eq('Band A or at its limit') | (df.env_state.str.startswith('Band B or C') & (df.vel < 1.0)))
    for label in RULES: df[label] = df[f'C::{label}'] | df[f'I::{label}']
    df['inv_any_operational'] = df[[f'I::{l}' for l in OPERATIONAL]].any(axis=1); df['comp_any_operational'] = df[[f'C::{l}' for l in OPERATIONAL]].any(axis=1); df['any_operational'] = df[OPERATIONAL].any(axis=1)
    df['upstream'] = df['Mine-level refrigeration (fridge plant, bulk air cooler, chilled water)']
    df['hts_class'] = df['hts_months'].map(lambda m: 'Not recorded' if pd.isna(m) else 'Chronology inconsistent' if m < 0 else '<=6 months' if m <= 6 else '7-12 months' if m <= 12 else '>12 months')
    df['wci_any'] = df.prev_episode.eq('Previous episode recorded') | df.acute_illness.eq('Yes or possible') | df.alcohol.eq('Within 48 h or affirmed') | df.med_control.eq('Poorly or partly controlled')
    df['wci_count'] = (df.prev_episode.eq('Previous episode recorded').astype(int) + df.acute_illness.eq('Yes or possible').astype(int) + df.alcohol.eq('Within 48 h or affirmed').astype(int) + df.med_control.eq('Poorly or partly controlled').astype(int))
    return df

def wilson(k, n):
    lo, hi = proportion_confint(k, n, method='wilson'); return f'{k}/{n} = {100*k/n:.0f}% (95% CI {100*lo:.0f}-{100*hi:.0f}%)' if n else '-'
def wilson_short(k, n):
    lo, hi = proportion_confint(k, n, method='wilson'); return f'{100*k/n:.0f}% ({100*lo:.0f}-{100*hi:.0f}%)' if n else '-'
def pct(n, d): return f'{n} ({100*n/d:.1f}%)' if d else '0'
def fisher(a, b, c, d):
    orr, p = stats.fisher_exact([[a, b], [c, d]])
    aa, bb, cc, dd = [x + 0.5 if min(a, b, c, d) == 0 else x for x in (a, b, c, d)]
    lor = np.log((aa * dd) / (bb * cc)); se = np.sqrt(1/aa + 1/bb + 1/cc + 1/dd)
    return orr, np.exp(lor - 1.96 * se), np.exp(lor + 1.96 * se), p
def mw(x, y):
    """Mann-Whitney with Hodges-Lehmann shift (x minus y) and rank-biserial r, positive when x tends to be higher than y."""
    u, p = stats.mannwhitneyu(x, y, alternative='two-sided'); hl = float(np.median([i - j for i in x for j in y])); rb = 2 * u / (len(x) * len(y)) - 1
    return u, p, hl, rb
def max3(dates):
    dates = np.sort(np.asarray(dates)); best = 0
    for i, d in enumerate(dates): best = max(best, int(np.searchsorted(dates, d + 2, side='right') - i))
    return best

def analyse(df, tag):
    OUT = f'{ROOT}/{tag}'; os.makedirs(OUT, exist_ok=True)
    N = len(df); a = df[df.complete]; hc = df[df.designation == 'Heat cramps']; bc = df[df.designation == 'Body cramps']
    S = {'N': N, 'mode': tag}
    # ---- Table I cohort
    if tag == 'main':   # the cleaned analysis set: the flags record what was corrected or removed
        cohort = [('Case rows in the register', 179), ('Rows removed as a duplicate of another row', 179 - N), ('Cases in the analysis set', N),
                  ('Case dates corrected from the diagnosis date and the recorded weekday', int(df.doa_flag.str.contains('inconsistent').sum())),
                  ('Diagnosis dates corrected (transposed or truncated entries read as intended)', int((df.dx_flag != '').sum())),
                  ('Recorded weekday disagrees with the case date (left as recorded)', int(df.doa_flag.str.contains('weekday').sum()))]
    else:               # the register as recorded: the flags are retained, nothing is corrected
        cohort = [('Case rows in the register', 179), ('Cases in this set', N), ('Candidate duplicate rows (flagged)', int(df.dup_candidate.sum())),
                  ('Case dates internally inconsistent with the diagnosis date (flagged)', int(df.doa_flag.str.contains('inconsistent').sum())),
                  ('Recorded weekday disagrees with case date (flagged)', int(df.doa_flag.str.contains('weekday').sum())), ('Diagnosis dates flagged for review', int((df.dx_flag != '').sum()))]
    cohort += [
              ('Cases dated 2023 / 2024', f"{int((df.year == 2023).sum())} / {int((df.year == 2024).sum())}"), ('Observed case dates', f"{df.doa.min():%d %b %Y} to {df.doa.max():%d %b %Y}"),
              ('Designation: heat cramps / body cramps / heat stroke / unclassified', ' / '.join(str(int((df.designation == k).sum())) for k in ['Heat cramps', 'Body cramps', 'Heat stroke', 'Unclassified'])),
              ('Shaft A / Shaft B', f"{int((df.shaft == 'A').sum())} / {int((df.shaft == 'B').sum())}"), ('Permanent / contractor', f"{int((df.employment == 'Permanent').sum())} / {int((df.employment == 'Contractor').sum())}"),
              ('Age, median (IQR), range', f"{df.Age.median():.0f} ({df.Age.quantile(.25):.0f}-{df.Age.quantile(.75):.0f}), {df.Age.min():.0f}-{df.Age.max():.0f}"),
              ('Workplace recorded', pct(int(df.workplace_recorded.sum()), N)), ('Level identified', pct(int(df.level.notna().sum()), N)), ('Raise line identified', pct(int(df.raise_code.notna().sum()), N)),
              ('Section recorded', pct(int(df.section_code.notna().sum()), N)), ('Shift recorded', pct(int(df['shift'].isin(['Day', 'Night']).sum()), N)),
              ('Wet-bulb, dry-bulb and velocity all recorded', pct(int(df.triplet.sum()), N)), ('Readings with a review flag (retained; excluded from environmental analyses)', int((df.qc_flag != '').sum())),
              ('Quality-valid environmental readings', pct(int(df.complete.sum()), N)), ('Employee complaint text present', pct(int(df.complaint_present.sum()), N)), ('Investigation statement present', pct(int((~df.inv_not_done).sum()), N)),
              ('Last heat-tolerance screening date usable (month or day precision)', pct(int(df.hts_months.notna().sum()), N))]
    pd.DataFrame(cohort, columns=['Measure', 'Result']).to_csv(f'{OUT}/T01_cohort.csv', index=False)
    df[df.qc_flag != ''][['case_id', 'wb', 'db', 'vel', 'qc_flag']].to_csv(f'{OUT}/T01b_flagged_velocity_readings.csv', index=False)
    df[(df.doa_flag != '') | (df.dx_flag != '') | df.dup_candidate][['case_id', 'doa_flag', 'dx_flag', 'dup_candidate']].to_csv(f'{OUT}/T01c_date_and_duplicate_flags.csv', index=False)
    # ---- Table II environment summary
    def env_summary(sub, label):
        s = sub[sub.complete]
        return {'Group': label, 'n': len(s), 'Wet-bulb C median (IQR)': f"{s.wb.median():.1f} ({s.wb.quantile(.25):.1f}-{s.wb.quantile(.75):.1f})", 'Dry-bulb C median (IQR)': f"{s.db.median():.1f} ({s.db.quantile(.25):.1f}-{s.db.quantile(.75):.1f})",
                'Velocity m/s median (IQR)': f"{s.vel.median():.2f} ({s.vel.quantile(.25):.2f}-{s.vel.quantile(.75):.2f})", 'Above or at the statutory limit': int((s.env_state == 'Band A or at its limit').sum()),
                'Velocity <0.25 m/s': int((s.vel < 0.25).sum()), 'Velocity <0.5 m/s': wilson_short(int((s.vel < 0.5).sum()), len(s)) if len(s) else '-', 'Velocity <1.0 m/s': wilson_short(int((s.vel < 1.0).sum()), len(s)) if len(s) else '-'}
    pd.DataFrame([env_summary(df, 'All cases'), env_summary(hc, 'Heat cramps'), env_summary(bc, 'Body cramps'), env_summary(df[df.shaft == 'A'], 'Shaft A'), env_summary(df[df.shaft == 'B'], 'Shaft B'), env_summary(df[df['shift'] == 'Day'], 'Day shift'), env_summary(df[df['shift'] == 'Night'], 'Night shift')]).to_csv(f'{OUT}/T02_environment_summary.csv', index=False)
    # velocity-reading sensitivity: including the 5.1 m/s high-value reading
    a51 = df[df.triplet & (df.qc_flag.isin(['', 'high-value review (above 5 m/s)']))].copy()
    a51['flag51'] = (a51.wb > 32.5) | (a51.db > 37.0) | (a51.wb == 32.5) | (a51.db == 37.0) | ((a51.wb > 27.5) & (a51.vel < 0.5)) | ((a51.wb <= 27.5) & (a51.db > 32.5) & (a51.vel < 0.5))
    pd.DataFrame([{'Analysis set': 'Quality-valid readings (principal)', 'n': len(a), 'Velocity <0.25 m/s': wilson(int((a.vel < 0.25).sum()), len(a)), 'Velocity <0.5 m/s': wilson(int((a.vel < 0.5).sum()), len(a)), 'Velocity <1.0 m/s': wilson(int((a.vel < 1.0).sum()), len(a)), 'Flagged by the review screen': wilson(int(a.review_flag.sum()), len(a))},
                  {'Analysis set': 'Including the high-value review reading (5.1 m/s)', 'n': len(a51), 'Velocity <0.25 m/s': wilson(int((a51.vel < 0.25).sum()), len(a51)), 'Velocity <0.5 m/s': wilson(int((a51.vel < 0.5).sum()), len(a51)), 'Velocity <1.0 m/s': wilson(int((a51.vel < 1.0).sum()), len(a51)), 'Flagged by the review screen': wilson(int(a51.flag51.sum()), len(a51))}]).to_csv(f'{OUT}/T02b_velocity_reading_sensitivity.csv', index=False)
    # ---- Table III bands x screens
    rows = []
    for b in ['Band A', 'Band B', 'Band C', 'Band D']:
        s = a[a.band == b]; rows.append({'DMPR band (numerical range)': b, 'Readings': wilson(len(s), len(a)), 'Velocity <0.25 m/s': int((s.vel < 0.25).sum()), 'Velocity 0.25-<0.5 m/s': int(((s.vel >= 0.25) & (s.vel < 0.5)).sum()), 'Velocity 0.5-<1.0 m/s': int(((s.vel >= 0.5) & (s.vel < 1.0)).sum()), 'Velocity >=1.0 m/s': int((s.vel >= 1.0).sum())})
    rows.append({'DMPR band (numerical range)': 'At the statutory limit (WB = 32.5 C or DB = 37.0 C), counted in Band B', 'Readings': str(int(a.at_band_a_limit.sum())), 'Velocity <0.25 m/s': '', 'Velocity 0.25-<0.5 m/s': '', 'Velocity 0.5-<1.0 m/s': '', 'Velocity >=1.0 m/s': ''})
    pd.DataFrame(rows).to_csv(f'{OUT}/T03_band_by_velocity.csv', index=False)
    pd.DataFrame([{'Environmental state at the recorded reading': st_, 'All cases': pct(int((df.env_state == st_).sum()), N), 'Heat cramps': pct(int((hc.env_state == st_).sum()), len(hc)), 'Body cramps': pct(int((bc.env_state == st_).sum()), len(bc))} for st_ in STATES]).to_csv(f'{OUT}/T03b_environment_state.csv', index=False)
    a[(a.band == 'Band A') | a.at_band_a_limit][['case_id', 'doa', 'shaft', 'level', 'wb', 'db', 'vel', 'designation', 'occ_group', 'band', 'at_band_a_limit']].to_csv(f'{OUT}/T03c_statutory_limit_records.csv', index=False)
    S['env'] = {'assessable': len(a), 'bandA': int((a.band == 'Band A').sum()), 'at_limit': int(a.at_band_a_limit.sum()), 'bandB': int((a.band == 'Band B').sum()), 'bandC': int((a.band == 'Band C').sum()), 'bandD': int((a.band == 'Band D').sum()),
                'v025': int((a.vel < 0.25).sum()), 'v05': int((a.vel < 0.5).sum()), 'v10': int((a.vel < 1.0).sum()), 'review': int(a.review_flag.sum()), 'review10': int(a.review_flag_10.sum()), 'wb_med': float(a.wb.median()), 'db_med': float(a.db.median()), 'vel_med': float(a.vel.median()),
                'v05_ci': wilson(int((a.vel < 0.5).sum()), len(a)), 'v10_ci': wilson(int((a.vel < 1.0).sum()), len(a)), 'v025_ci': wilson(int((a.vel < 0.25).sum()), len(a)), 'review_ci': wilson(int(a.review_flag.sum()), len(a)), 'review10_ci': wilson(int(a.review_flag_10.sum()), len(a)),
                'within_ci': wilson(int((a.env_state == 'Band B or C; velocity >=0.5 m/s').sum()), len(a)), 'states': {st_: int((df.env_state == st_).sum()) for st_ in STATES},
                'shaft_v05': {s_: (int((a[a.shaft == s_].vel < 0.5).sum()), int((a.shaft == s_).sum())) for s_ in ('A', 'B')}, 'a51_n': len(a51), 'a51_v05': wilson(int((a51.vel < 0.5).sum()), len(a51))}
    # ---- family 1: environmental contrasts
    fam1 = []; aA, aB = a[a.shaft == 'A'], a[a.shaft == 'B']
    for thr, lab in [(0.5, 'velocity <0.5 m/s'), (1.0, 'velocity <1.0 m/s')]:
        k1, n1, k2, n2 = int((aA.vel < thr).sum()), len(aA), int((aB.vel < thr).sum()), len(aB); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
        fam1.append(('Environment', f'Shaft A vs Shaft B: {lab}', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    k1, n1, k2, n2 = int((a[a['shift'] == 'Night'].vel < 0.5).sum()), int((a['shift'] == 'Night').sum()), int((a[a['shift'] == 'Day'].vel < 0.5).sum()), int((a['shift'] == 'Day').sum()); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
    fam1.append(('Environment', 'Night vs day shift: velocity <0.5 m/s', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    u, p, hl, rb = mw(a[a['shift'] == 'Night'].wb, a[a['shift'] == 'Day'].wb)
    fam1.append(('Environment', 'Night vs day shift: wet-bulb temperature', f'medians {a[a["shift"] == "Night"].wb.median():.1f} vs {a[a["shift"] == "Day"].wb.median():.1f} C', f'Hodges-Lehmann shift {hl:+.1f} C; rank-biserial r {rb:+.2f}', 'Mann-Whitney', p))
    k1, n1, k2, n2 = int((a[a.review_flag].any_operational).sum()), int(a.review_flag.sum()), int((a[~a.review_flag].any_operational).sum()), int((~a.review_flag).sum()); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
    fam1.append(('Environment', 'Operational documentary mention (either source): readings flagged by the review screen vs not flagged', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    vm = a[a['I::Ventilation controls absent or substandard']].vel; vn = a[~a['I::Ventilation controls absent or substandard']].vel; u, p, hl, rb = mw(vm, vn)
    fam1.append(('Environment', 'Air velocity: investigation codes ventilation controls vs not', f'medians {vm.median():.2f} vs {vn.median():.2f} m/s', f'Hodges-Lehmann shift {hl:+.2f} m/s; rank-biserial r {rb:+.2f}', 'Mann-Whitney', p))
    S['vent_velocity'] = {'med_yes': float(vm.median()), 'med_no': float(vn.median()), 'hl': hl, 'rb': rb, 'p': float(p)}
    # ---- operational: occupation, weekday, shift, month, season
    occ_order = ['Stoping and production', 'Scraping and winching', 'Development and raise work', 'Transport, loading and cleaning', 'Blasting and charging', 'Engineering and services', 'Supervision']
    pd.DataFrame([{'Occupation group': g, 'All cases': pct(int((df.occ_group == g).sum()), N), 'Heat cramps': pct(int((hc.occ_group == g).sum()), len(hc)), 'Body cramps': pct(int((bc.occ_group == g).sum()), len(bc)),
                   'Velocity <0.5 m/s / assessable': f"{int((a[a.occ_group == g].vel < 0.5).sum())}/{int((a.occ_group == g).sum())}", 'Previous episode recorded': pct(int(((df.occ_group == g) & df.prev_episode.eq('Previous episode recorded')).sum()), int((df.occ_group == g).sum()))} for g in occ_order]).to_csv(f'{OUT}/T05_occupation.csv', index=False)
    days = pd.Series(pd.date_range(df.doa.min(), df.doa.max())).dt.day_name().value_counts()
    pd.DataFrame([{'Weekday of case date': w, 'Calendar days': int(days.get(w, 0)), 'All cases': pct(int((df.weekday == w).sum()), N), 'Heat cramps': pct(int((hc.weekday == w).sum()), len(hc)), 'Body cramps': pct(int((bc.weekday == w).sum()), len(bc)),
                   'Alcohol <=48 h or affirmed': int(((df.weekday == w) & df.alcohol.eq('Within 48 h or affirmed')).sum()), 'Previous episode': int(((df.weekday == w) & df.prev_episode.eq('Previous episode recorded')).sum()),
                   'Velocity <0.5 m/s / assessable': f"{int((a[a.weekday == w].vel < 0.5).sum())}/{int((a.weekday == w).sum())}", 'Night shift': int(((df.weekday == w) & (df['shift'] == 'Night')).sum())} for w in WK]).to_csv(f'{OUT}/T06_weekday.csv', index=False)
    pd.DataFrame([{'Shift': s_, 'All cases': pct(int((df['shift'] == s_).sum()), N), 'Heat cramps': pct(int((hc['shift'] == s_).sum()), len(hc)), 'Body cramps': pct(int((bc['shift'] == s_).sum()), len(bc)), 'Velocity <0.5 m/s / assessable': f"{int((a[a['shift'] == s_].vel < 0.5).sum())}/{int((a['shift'] == s_).sum())}"} for s_ in ['Day', 'Night', 'Not recorded']]).to_csv(f'{OUT}/T06b_shift.csv', index=False)
    monthly = df.groupby('month').size().rename('cases').reset_index(); monthly.to_csv(f'{OUT}/T06c_monthly.csv', index=False)
    pd.DataFrame([{'Season': s_, 'All cases': pct(int((df.season == s_).sum()), N), 'Heat cramps': pct(int((hc.season == s_).sum()), len(hc)), 'Body cramps': pct(int((bc.season == s_).sum()), len(bc))} for s_ in ['Summer', 'Autumn', 'Winter', 'Spring']]).to_csv(f'{OUT}/T06d_season.csv', index=False)
    # ---- calendar models on daily counts
    cstart = pd.Timestamp(COVERAGE_START) if COVERAGE_START else pd.Timestamp(df.doa.min()); cend = pd.Timestamp(COVERAGE_END) if COVERAGE_END else pd.Timestamp(df.doa.max())
    cal = pd.DataFrame({'date': pd.date_range(cstart, cend)}); cnt = df.groupby('doa').size(); cal['y'] = cal.date.map(lambda d: int(cnt.get(d.date(), 0)))
    cal['weekday'] = pd.Categorical(cal.date.dt.day_name(), categories=['Friday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Saturday', 'Sunday']); cal['year'] = cal.date.dt.year.astype(str); doy = cal.date.dt.dayofyear
    cal['sin'] = np.sin(2 * np.pi * doy / 365.25); cal['cos'] = np.cos(2 * np.pi * doy / 365.25); cal['pay'] = (cal.date.dt.day >= 25).astype(int)
    cal['grp'] = pd.Categorical(cal.date.dt.day_name().map(lambda w: 'Mon-Tue' if w in ('Monday', 'Tuesday') else 'Wed-Fri' if w in ('Wednesday', 'Thursday', 'Friday') else 'Weekend'), categories=['Wed-Fri', 'Mon-Tue', 'Weekend'])
    cal['week'] = cal.date.dt.to_period('W').astype(str)
    F = 'y ~ C(weekday) + C(year) + sin + cos + pay'
    pois = smf.glm(F, data=cal, family=sm.families.Poisson()).fit(cov_type='HC1'); disp = float((pois.resid_pearson ** 2).sum() / pois.df_resid)
    ci = pois.conf_int(); pm = pd.DataFrame({'term': pois.params.index, 'rate_ratio': np.exp(pois.params.values), 'ci_low': np.exp(ci[0].values), 'ci_high': np.exp(ci[1].values), 'p': pois.pvalues.values}); pm['dispersion'] = disp; pm.to_csv(f'{OUT}/T06e_poisson_calendar_model.csv', index=False)
    S['poisson'] = {t: (float(np.exp(pois.params[t])), float(np.exp(ci.loc[t, 0])), float(np.exp(ci.loc[t, 1])), float(pois.pvalues[t])) for t in pois.params.index}; S['poisson']['dispersion'] = disp
    # robustness: quasi-Poisson (Pearson scale), negative binomial (NB2, alpha by ML), week-block bootstrap, grouped-weekday model
    qp = smf.glm(F, data=cal, family=sm.families.Poisson()).fit(scale='X2'); qci = qp.conf_int()
    nb = smf.negativebinomial(F, data=cal).fit(disp=0, maxiter=200); nci = nb.conf_int()
    grp = smf.glm('y ~ C(grp) + C(year) + sin + cos + pay', data=cal, family=sm.families.Poisson()).fit(cov_type='HC1'); gci = grp.conf_int()
    rng = np.random.default_rng(SEED); weeks = cal.week.unique(); boots = {'Tuesday': [], 'Monday': [], 'MonTue': []}
    for _ in range(NBOOT):
        samp = pd.concat([cal[cal.week == w] for w in rng.choice(weeks, size=len(weeks), replace=True)])
        try:
            m1 = smf.glm(F, data=samp, family=sm.families.Poisson()).fit(); m2 = smf.glm('y ~ C(grp) + C(year) + sin + cos + pay', data=samp, family=sm.families.Poisson()).fit()
            boots['Tuesday'].append(np.exp(m1.params['C(weekday)[T.Tuesday]'])); boots['Monday'].append(np.exp(m1.params['C(weekday)[T.Monday]'])); boots['MonTue'].append(np.exp(m2.params['C(grp)[T.Mon-Tue]']))
        except Exception: pass
    rob = []
    for lab, t in [('Tuesday vs Friday', 'C(weekday)[T.Tuesday]'), ('Monday vs Friday', 'C(weekday)[T.Monday]'), ('Days 25-31 vs other days', 'pay')]:
        rob.append({'Contrast': lab, 'Poisson, robust (HC1) SE': f"{np.exp(pois.params[t]):.2f} ({np.exp(ci.loc[t, 0]):.2f}-{np.exp(ci.loc[t, 1]):.2f})", 'Quasi-Poisson (Pearson dispersion)': f"{np.exp(qp.params[t]):.2f} ({np.exp(qci.loc[t, 0]):.2f}-{np.exp(qci.loc[t, 1]):.2f})",
                    'Negative binomial (NB2)': f"{np.exp(nb.params[t]):.2f} ({np.exp(nci.loc[t, 0]):.2f}-{np.exp(nci.loc[t, 1]):.2f})", 'Week-block bootstrap 95% percentile interval': (f"{np.percentile(boots['Tuesday' if 'Tuesday' in lab else 'Monday'], 2.5):.2f}-{np.percentile(boots['Tuesday' if 'Tuesday' in lab else 'Monday'], 97.5):.2f}" if 'Friday' in lab else '-')})
    t = 'C(grp)[T.Mon-Tue]'
    rob.append({'Contrast': 'Monday-Tuesday vs Wednesday-Friday (grouped model)', 'Poisson, robust (HC1) SE': f"{np.exp(grp.params[t]):.2f} ({np.exp(gci.loc[t, 0]):.2f}-{np.exp(gci.loc[t, 1]):.2f})", 'Quasi-Poisson (Pearson dispersion)': '-', 'Negative binomial (NB2)': '-', 'Week-block bootstrap 95% percentile interval': f"{np.percentile(boots['MonTue'], 2.5):.2f}-{np.percentile(boots['MonTue'], 97.5):.2f}"})
    pd.DataFrame(rob).to_csv(f'{OUT}/T06f_weekday_model_robustness.csv', index=False)
    S['robust'] = {'dispersion': disp, 'nb_alpha': float(nb.params['alpha']) if 'alpha' in nb.params else None, 'montue_rr': (float(np.exp(grp.params[t])), float(np.exp(gci.loc[t, 0])), float(np.exp(gci.loc[t, 1])), float(grp.pvalues[t])), 'montue_boot': (float(np.percentile(boots['MonTue'], 2.5)), float(np.percentile(boots['MonTue'], 97.5))),
                   'tue_boot': (float(np.percentile(boots['Tuesday'], 2.5)), float(np.percentile(boots['Tuesday'], 97.5))), 'mon_boot': (float(np.percentile(boots['Monday'], 2.5)), float(np.percentile(boots['Monday'], 97.5))), 'nb_tue': (float(np.exp(nb.params['C(weekday)[T.Tuesday]'])), float(np.exp(nci.loc['C(weekday)[T.Tuesday]', 0])), float(np.exp(nci.loc['C(weekday)[T.Tuesday]', 1]))),
                   'qp_tue': (float(np.exp(qp.params['C(weekday)[T.Tuesday]'])), float(np.exp(qci.loc['C(weekday)[T.Tuesday]', 0])), float(np.exp(qci.loc['C(weekday)[T.Tuesday]', 1]))), 'nboot_ok': len(boots['MonTue'])}
    o = np.array([int((df.weekday == w).sum()) for w in WK[:5]]); e = np.array([days[w] for w in WK[:5]]) / sum(days[w] for w in WK[:5]) * o.sum(); chi, p = stats.chisquare(o, e)
    fam2 = [('Operational', 'Weekday distribution Monday-Friday vs calendar days (Friday-independent)', 'Mon ' + ', '.join(f'{w[:3]} {int(k)}' for w, k in zip(WK[:5], o))[4:], f'chi-square {chi:.1f} (4 df)', 'Chi-square goodness of fit', p)]
    fam2.append(('Operational', 'Monday-Tuesday vs Wednesday-Friday (calendar count ratio, grouped Poisson model)', f"RR {S['robust']['montue_rr'][0]:.2f}", f"95% CI {S['robust']['montue_rr'][1]:.2f}-{S['robust']['montue_rr'][2]:.2f}", 'Poisson GLM, robust SE', S['robust']['montue_rr'][3]))
    for t_, lab in [('C(weekday)[T.Tuesday]', 'Tuesday vs Friday (calendar count ratio, Poisson model)'), ('C(weekday)[T.Monday]', 'Monday vs Friday (calendar count ratio, Poisson model)'), ('pay', 'Days 25-31 vs other days (calendar count ratio, Poisson model)')]:
        rr, lo, hi, p = S['poisson'][t_]; fam2.append(('Operational', lab, f'RR {rr:.2f}', f'95% CI {lo:.2f}-{hi:.2f}', 'Poisson GLM, robust SE', p))
    mon = df[df.weekday == 'Monday']; oth = df[df.weekday != 'Monday']
    k1, n1, k2, n2 = int(mon.alcohol.eq('Within 48 h or affirmed').sum()), len(mon), int(oth.alcohol.eq('Within 48 h or affirmed').sum()), len(oth); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
    fam2.append(('Operational', 'Alcohol <=48 h or affirmed, documented: Monday vs other days', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    # sensitivity: explicit timing only (bare 'yes'/'possible' entries excluded)
    ex = df.alcohol.eq('Within 48 h or affirmed') & df.alcohol_timing.eq('explicit timing'); bare = df.alcohol.eq('Within 48 h or affirmed') & df.alcohol_timing.eq('affirmed without timing')
    e1, m1, e2, m2 = int((ex & (df.weekday == 'Monday')).sum()), int((df.weekday == 'Monday').sum()), int((ex & (df.weekday != 'Monday')).sum()), int((df.weekday != 'Monday').sum()); orx, lox, hix, px = fisher(e1, m1 - e1, e2, m2 - e2)
    pd.DataFrame([{'Class': 'Documented within ~48 h or affirmed (all)', 'n': int(df.alcohol.eq('Within 48 h or affirmed').sum()), 'Monday': k1, 'Other days': k2, 'OR Monday vs other (95% CI)': f'{orr:.1f} ({lo:.1f}-{hi:.1f})', 'p (Fisher)': f'{p:.2g}'},
                  {'Class': 'Explicit timing only', 'n': int(ex.sum()), 'Monday': e1, 'Other days': e2, 'OR Monday vs other (95% CI)': f'{orx:.1f} ({lox:.1f}-{hix:.1f})', 'p (Fisher)': f'{px:.2g}'},
                  {'Class': 'Affirmed without timing (bare yes/possible)', 'n': int(bare.sum()), 'Monday': int((bare & (df.weekday == 'Monday')).sum()), 'Other days': int((bare & (df.weekday != 'Monday')).sum()), 'OR Monday vs other (95% CI)': '-', 'p (Fisher)': '-'}]).to_csv(f'{OUT}/T06g_alcohol_explicit_timing_sensitivity.csv', index=False)
    S['alcohol_timing'] = {'all': int(df.alcohol.eq('Within 48 h or affirmed').sum()), 'explicit': int(ex.sum()), 'bare': int(bare.sum()), 'explicit_monday': (e1, m1, e2, m2), 'explicit_or': (float(orx), float(lox), float(hix), float(px)), 'explicit_tuesday': int((ex & (df.weekday == 'Tuesday')).sum())}
    tue = df[df.weekday == 'Tuesday']; k1, n1 = int(tue.alcohol.eq('Within 48 h or affirmed').sum()), len(tue); k2, n2 = int(df[~df.weekday.isin(['Monday', 'Tuesday'])].alcohol.eq('Within 48 h or affirmed').sum()), int((~df.weekday.isin(['Monday', 'Tuesday'])).sum()); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
    fam2.append(('Operational', 'Alcohol <=48 h or affirmed, documented: Tuesday vs Wednesday-Sunday', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    S['alc_by_weekday'] = {w: int(((df.weekday == w) & df.alcohol.eq('Within 48 h or affirmed')).sum()) for w in WK}; S['weekday'] = {w: int((df.weekday == w).sum()) for w in WK}
    # ---- place
    lvl = pd.crosstab([df.shaft, df.level.fillna('Roving/unknown')], df.designation).reset_index(); lvl['Total'] = lvl[[c for c in lvl.columns if c in ('Heat cramps', 'Body cramps', 'Heat stroke', 'Unclassified')]].sum(axis=1); lvl.to_csv(f'{OUT}/T07_shaft_level.csv', index=False)
    rl = df[df.raise_code.notna()].groupby('raise_code').agg(cases=('case_id', 'size'), shaft=('shaft', 'first'), level=('level', 'first'), first=('doa', 'min'), last=('doa', 'max'),
        vent_controls=('I::Ventilation controls absent or substandard', 'sum'), obstruction=('I::Ore or material accumulation obstructing airflow', 'sum'), local_cooling=('I::Local cooling equipment (cooling car, in-stope cooler)', 'sum'),
        mine_refrig=('upstream', 'sum'), vel_deficient=('vel', lambda v: int((v < 0.5).sum())), assessable=('complete', 'sum'), prev_episode=('prev_episode', lambda s: int((s == 'Previous episode recorded').sum()))).reset_index().sort_values(['cases', 'raise_code'], ascending=[False, True])
    rl.to_csv(f'{OUT}/T07b_raise_lines.csv', index=False)
    sec = df[df.section_code.notna()].groupby('section_code').agg(cases=('case_id', 'size'), shaft=('shaft', lambda s: '/'.join(sorted(set(s)))), levels=('level', lambda s: '/'.join(sorted(set(x for x in s if isinstance(x, str))))), vent_controls=('I::Ventilation controls absent or substandard', 'sum'), vel_deficient=('vel', lambda v: int((v < 0.5).sum())), assessable=('complete', 'sum')).reset_index().sort_values('cases', ascending=False)
    sec.to_csv(f'{OUT}/T07c_sections.csv', index=False)
    S['raise_top'] = rl.head(10)[['raise_code', 'cases']].values.tolist(); S['raise_assigned'] = int(df.raise_code.notna().sum()); S['section_top'] = sec.head(5)[['section_code', 'cases']].values.tolist()
    S['level_by_shaft'] = {f'{s}-{l}': int(n) for (s, l), n in df.groupby(['shaft', df.level.fillna('roving')]).size().items()}
    # ---- short-window concentrations (descriptive scan probabilities, unadjusted)
    events = []
    for (s, l), g in df[df.level.notna()].groupby(['shaft', 'level']):
        dates = sorted(g.doa)
        for d0 in dates:
            win = [d for d in dates if 0 <= (d - d0).days <= 2]
            if len(win) >= 3: events.append((s, l, d0, max(win)))
    merged = []
    for e in sorted(set(events)):
        if merged and merged[-1][0] == e[0] and merged[-1][1] == e[1] and (e[2] - merged[-1][3]).days <= 1: merged[-1] = [e[0], e[1], merged[-1][2], max(merged[-1][3], e[3])]
        else: merged.append(list(e))
    ndays = (df.doa.max() - df.doa.min()).days + 1; cl_rows = []
    for s, l, d0, d1 in merged:
        g = df[(df.shaft == s) & (df.level == l) & (df.doa >= d0) & (df.doa <= d1)]; nlvl = int(((df.shaft == s) & (df.level == l)).sum()); lam = nlvl / ndays * 3
        maxwin = max(len([d for d in g.doa if 0 <= (d - dd).days <= 2]) for dd in g.doa); classes = [c for c in OPERATIONAL if g[f'I::{c}'].any()]
        cl_rows.append({'Shaft-level': f'{s}-{l}', 'Window': f'{d0:%d %b %Y}' + (f' to {d1:%d %b %Y}' if d1 != d0 else ''), 'Cases': len(g), 'Max in any 3 days': maxwin, 'Raise lines': g.raise_code.nunique(), 'Velocity <0.5 m/s / assessable': f"{int((g.vel < 0.5).sum())}/{int(g.complete.sum())}",
                        'Above or at the statutory limit': int((g.env_state == 'Band A or at its limit').sum()), f'Investigation statements (coded, {CODE_LABEL})': '; '.join(classes), 'Mine-level refrigeration coded': int(g.upstream.sum()), 'Investigations present': int((~g.inv_not_done).sum()),
                        'Level cases / 3-day expectation': f'{nlvl} cases; lambda = {lam:.2f}', 'Descriptive Poisson P(>= observed in a 3-day window), unadjusted': f'{stats.poisson.sf(maxwin - 1, lam):.1e}'})
    pd.DataFrame(cl_rows).to_csv(f'{OUT}/T08_cluster_windows.csv', index=False); S['clusters'] = cl_rows
    # ---- two permutation nulls for the largest three-day count per level
    rng = np.random.default_rng(SEED); rngB = np.random.default_rng(SEED + 1); levels = df[df.level.notna()].groupby(['shaft', 'level']).size()
    caldays = pd.date_range(df.doa.min(), df.doa.max()); mcount = df.groupby('month').size(); wcount = df.weekday.value_counts(); wdays = pd.Series(caldays.day_name()).value_counts()
    w = np.array([(mcount.get(d.strftime('%Y-%m'), 0) / caldays[(caldays.year == d.year) & (caldays.month == d.month)].size) * (wcount.get(d.day_name(), 0) / wdays[d.day_name()]) for d in caldays], dtype=float); w = w / w.sum()
    pooled = np.array([d.toordinal() for d in caldays]); draw = lambda n: rng.choice(pooled, size=n, replace=True, p=w)
    obs = {k: max3([d.toordinal() for d in df[(df.shaft == k[0]) & (df.level == k[1])].doa]) for k in levels.index}
    simsA = {k: np.zeros(NPERM, dtype=int) for k in levels.index}; anyA = np.zeros(NPERM, dtype=int)
    for p_ in range(NPERM):
        mx = 0
        for k, n in levels.items(): v = max3(draw(n)); simsA[k][p_] = v; mx = max(mx, v)
        anyA[p_] = mx
    dl = df[df.level.notna()]; dates_all = np.array([d.toordinal() for d in dl.doa]); labs = np.array([f'{s}-{l}' for s, l in zip(dl.shaft, dl.level)])
    simsB = {k: np.zeros(NPERM, dtype=int) for k in levels.index}; anyB = np.zeros(NPERM, dtype=int)
    for p_ in range(NPERM):
        perm = rngB.permutation(labs); mx = 0
        for k in levels.index: v = max3(dates_all[perm == f'{k[0]}-{k[1]}']); simsB[k][p_] = v; mx = max(mx, v)
        anyB[p_] = mx
    perm_rows = []
    for k, n in levels.items():
        if n < 10: continue
        perm_rows.append({'Shaft-level': f'{k[0]}-{k[1]}', 'Cases': int(n), 'Observed largest 3-day count': obs[k], 'Null A mean': f'{simsA[k].mean():.2f}', 'Null A 95th percentile': int(np.percentile(simsA[k], 95)), 'P (null A: pooled-calendar re-dating)': f'{(simsA[k] >= obs[k]).mean():.4f}',
                          'Null B mean': f'{simsB[k].mean():.2f}', 'Null B 95th percentile': int(np.percentile(simsB[k], 95)), 'P (null B: exact-date level allocation)': f'{(simsB[k] >= obs[k]).mean():.4f}'})
    mo = max(obs.values())
    perm_rows.append({'Shaft-level': 'Any level (maximum over all levels)', 'Cases': int(levels.sum()), 'Observed largest 3-day count': mo, 'Null A mean': f'{anyA.mean():.2f}', 'Null A 95th percentile': int(np.percentile(anyA, 95)), 'P (null A: pooled-calendar re-dating)': f'{(anyA >= mo).mean():.4f}', 'Null B mean': f'{anyB.mean():.2f}', 'Null B 95th percentile': int(np.percentile(anyB, 95)), 'P (null B: exact-date level allocation)': f'{(anyB >= mo).mean():.4f}'})
    pd.DataFrame(perm_rows).to_csv(f'{OUT}/T08b_permutation_tests.csv', index=False); S['perm'] = perm_rows
    # ---- coded statements by source
    dm = []
    for label in RULES:
        c_, i_ = int(df[f'C::{label}'].sum()), int(df[f'I::{label}'].sum()); either = int(df[label].sum()); sub = a[a[f'I::{label}']]
        dm.append({f'Coded statement ({CODE_LABEL})': label, 'Complaint text': pct(c_, N), 'Investigation text': pct(i_, N), 'Either source': pct(either, N), 'Heat cramps (either)': pct(int(hc[label].sum()), len(hc)), 'Body cramps (either)': pct(int(bc[label].sum()), len(bc)),
                   'Velocity <0.5 m/s / assessable (investigation-coded)': f"{int((sub.vel < 0.5).sum())}/{len(sub)}" if len(sub) else '-', 'Wet-bulb C median (investigation-coded)': f"{sub.wb.median():.1f}" if len(sub) else '-'})
    dm.append({f'Coded statement ({CODE_LABEL})': 'Investigation not done, not applicable or blank', 'Complaint text': '', 'Investigation text': pct(int(df.inv_not_done.sum()), N), 'Either source': '', 'Heat cramps (either)': pct(int(hc.inv_not_done.sum()), len(hc)), 'Body cramps (either)': pct(int(bc.inv_not_done.sum()), len(bc)), 'Velocity <0.5 m/s / assessable (investigation-coded)': '', 'Wet-bulb C median (investigation-coded)': ''})
    pd.DataFrame(dm).to_csv(f'{OUT}/T09_documentary_mentions.csv', index=False)
    S['mentions'] = {label: {'C': int(df[f'C::{label}'].sum()), 'I': int(df[f'I::{label}'].sum()), 'either': int(df[label].sum()), 'hc_I': int(hc[f'I::{label}'].sum())} for label in RULES}
    S['inv_not_done'] = int(df.inv_not_done.sum()); S['inv_not_done_bc'] = int(bc.inv_not_done.sum()); S['any_operational_I'] = int(df.inv_any_operational.sum()); S['any_operational_either'] = int(df.any_operational.sum()); S['matches_total'] = int(sum(int(df[f'{s}::{l}'].sum()) for l in RULES for s in ('C', 'I')))
    # ---- worker-context indicators
    def ft(col, order, field):
        return [{'Field': field, 'Recorded value': ('Within approximately 48 h or affirmed without timing' if c_ == 'Within 48 h or affirmed' else c_), 'All cases': pct(int((df[col] == c_).sum()), N), 'Heat cramps': pct(int((hc[col] == c_).sum()), len(hc)), 'Body cramps': pct(int((bc[col] == c_).sum()), len(bc))} for c_ in order]
    pf = ft('prev_episode', ['Previous episode recorded', 'None recorded', 'Not recorded'], 'Previous episodes') + ft('med_condition', ['Yes', 'No'], 'Medical condition') + ft('med_control', ['Controlled or acceptable', 'Poorly or partly controlled', 'Control not known', 'No condition recorded'], 'Control of medical condition') + \
         ft('alcohol', ['Sober habits or no recent use', 'More than 48 h before', 'Within 48 h or affirmed', 'Not recorded'], 'Recent alcohol use (documented)') + ft('acute_illness', ['Yes or possible', 'No'], 'Acute illness at the time') + ft('hts_class', ['<=6 months', '7-12 months', '>12 months', 'Chronology inconsistent', 'Not recorded'], 'Months since last heat-tolerance screening')
    pd.DataFrame(pf).to_csv(f'{OUT}/T10_worker_context.csv', index=False)
    hv = df.hts_months[df.hts_months >= 0]
    S['hts'] = {'usable': int(df.hts_months.notna().sum()), 'valid': int(len(hv)), 'median': float(hv.median()), 'q1': float(hv.quantile(.25)), 'q3': float(hv.quantile(.75)), 'le6': int((hv <= 6).sum()), 'le12': int((hv <= 12).sum()), 'gt12': int((hv > 12).sum()), 'inconsistent': int((df.hts_months < 0).sum()), 'precision': df.hts_precision.value_counts().to_dict()}
    S['personal'] = {'prev': int(df.prev_episode.eq('Previous episode recorded').sum()), 'prev_known': int((df.prev_episode != 'Not recorded').sum()), 'med': int(df.med_condition.eq('Yes').sum()), 'ctrl': df.med_control.value_counts().to_dict(), 'alc': df.alcohol.value_counts().to_dict(), 'acute': int(df.acute_illness.eq('Yes or possible').sum()),
                     'any': int(df.wci_any.sum()), 'count': {str(k): int(v) for k, v in df.wci_count.value_counts().sort_index().items()},
                     'by_desig': {d: {'n': len(g), 'prev': int(g.prev_episode.eq('Previous episode recorded').sum()), 'prev_known': int((g.prev_episode != 'Not recorded').sum()), 'acute': int(g.acute_illness.eq('Yes or possible').sum()), 'alc48': int(g.alcohol.eq('Within 48 h or affirmed').sum()), 'alc_known': int((g.alcohol != 'Not recorded').sum()), 'medyes': int(g.med_condition.eq('Yes').sum()), 'medpoor': int(g.med_control.eq('Poorly or partly controlled').sum())} for d, g in df.groupby('designation')}}
    fam3 = []
    for lab, col, val, known in [('Previous episode recorded', 'prev_episode', 'Previous episode recorded', lambda g: g.prev_episode != 'Not recorded'), ('Acute illness recorded', 'acute_illness', 'Yes or possible', lambda g: g.acute_illness != 'Not recorded'), ('Alcohol <=48 h or affirmed, documented', 'alcohol', 'Within 48 h or affirmed', lambda g: g.alcohol != 'Not recorded'), ('Medical condition recorded', 'med_condition', 'Yes', lambda g: g.med_condition != 'Not recorded')]:
        h_, b_ = hc[known(hc)], bc[known(bc)]; k1, n1, k2, n2 = int((h_[col] == val).sum()), len(h_), int((b_[col] == val).sum()), len(b_); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2)
        fam3.append(('Worker context', f'{lab}: heat cramps vs body cramps', f'{k1}/{n1} vs {k2}/{n2}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    t11 = pd.crosstab(a.review_flag.map({True: FLAG, False: NOFLAG}), a.wci_any.map({True: WCI, False: NOWCI})).reindex(index=[FLAG, NOFLAG]); t11.to_csv(f'{OUT}/T11_environment_by_worker_context.csv')
    S['t11'] = {str(k): {str(kk): int(vv) for kk, vv in v.items()} for k, v in t11.to_dict().items()}; S['neither_hc'] = int(((a.designation == 'Heat cramps') & ~a.review_flag & ~a.wci_any).sum())
    orr, lo, hi, p = fisher(int((a.review_flag & a.wci_any).sum()), int((a.review_flag & ~a.wci_any).sum()), int((~a.review_flag & a.wci_any).sum()), int((~a.review_flag & ~a.wci_any).sum()))
    fam3.append(('Worker context', 'Recorded worker-context indicator: readings flagged by the review screen vs not flagged', f'{int((a.review_flag & a.wci_any).sum())}/{int(a.review_flag.sum())} vs {int((~a.review_flag & a.wci_any).sum())}/{int((~a.review_flag).sum())}', f'OR {orr:.1f} ({lo:.1f}-{hi:.1f})', 'Fisher exact', p))
    FLAG10 = 'Flagged at the 1.0 m/s upper screen (above or at the statutory limit, or velocity <1.0 m/s)'; NOFLAG10 = 'Within the 1.0 m/s upper screen'
    t11b = pd.crosstab(a.review_flag_10.map({True: FLAG10, False: NOFLAG10}), a.wci_any.map({True: WCI, False: NOWCI})).reindex(index=[FLAG10, NOFLAG10]); t11b.to_csv(f'{OUT}/T11b_environment_by_worker_context_1_0_screen.csv')
    orr10, lo10, hi10, p10 = fisher(int((a.review_flag_10 & a.wci_any).sum()), int((a.review_flag_10 & ~a.wci_any).sum()), int((~a.review_flag_10 & a.wci_any).sum()), int((~a.review_flag_10 & ~a.wci_any).sum()))
    S['t11b'] = {'neither': int((~a.review_flag_10 & ~a.wci_any).sum()), 'neither_ci': wilson(int((~a.review_flag_10 & ~a.wci_any).sum()), len(a)), 'or': (float(orr10), float(lo10), float(hi10), float(p10)), 'table': {str(k): {str(kk): int(vv) for kk, vv in v.items()} for k, v in t11b.to_dict().items()}}
    S['neither_ci'] = wilson(int((~a.review_flag & ~a.wci_any).sum()), len(a))
    # ---- BH within primary families
    rows = []
    for fam in (fam1, fam2, fam3):
        ps = [x[5] for x in fam]; q = multipletests(ps, method='fdr_bh')[1]
        for x, qq in zip(fam, q): rows.append({'Family': x[0], 'Contrast': x[1], 'Data': x[2], 'Estimate': x[3], 'Test': x[4], 'p': f'{x[5]:.3g}', 'q (BH within family)': f'{qq:.3g}'})
    pd.DataFrame(rows).to_csv(f'{OUT}/T12_statistical_tests.csv', index=False); S['tests'] = rows
    # ---- supplementary S4: designation comparisons (exploratory family)
    sup = []
    for lab, col in [('Age (years)', 'Age'), ('Wet-bulb temperature (C)', 'wb'), ('Dry-bulb temperature (C)', 'db'), ('Air velocity (m/s)', 'vel'), ('Months since last HTS', 'hts_months')]:
        src = a if col in ('wb', 'db', 'vel') else df
        x = src[src.designation == 'Heat cramps'][col].dropna(); y = src[src.designation == 'Body cramps'][col].dropna()
        if col == 'hts_months': x, y = x[x >= 0], y[y >= 0]
        u, p, hl, rb = mw(x, y)
        sup.append({'Variable': lab, 'Heat cramps n; median (IQR)': f'{len(x)}; {x.median():.2f} ({x.quantile(.25):.2f}-{x.quantile(.75):.2f})', 'Body cramps n; median (IQR)': f'{len(y)}; {y.median():.2f} ({y.quantile(.25):.2f}-{y.quantile(.75):.2f})', 'Hodges-Lehmann difference (heat cramps minus body cramps)': f'{hl:.2f}', 'Rank-biserial r (positive: heat cramps higher)': f'{rb:.2f}', 'p (Mann-Whitney)': p})
    q = multipletests([r['p (Mann-Whitney)'] for r in sup], method='fdr_bh')[1]
    for r, qq in zip(sup, q): r['q (BH, exploratory designation family)'] = f'{qq:.3f}'; r['p (Mann-Whitney)'] = f"{r['p (Mann-Whitney)']:.3f}"
    pd.DataFrame(sup).to_csv(f'{OUT}/S4a_designation_continuous.csv', index=False); S['S4a'] = sup
    cat = []; hb = df[df.designation.isin(['Heat cramps', 'Body cramps'])]
    for fac_name, ser in [('Season', hb.season), ('Occupation (production vs other)', hb.occ_group.isin(['Stoping and production', 'Scraping and winching', 'Development and raise work']).map({True: 'Production', False: 'Other'})), ('Shift (day/night/not recorded)', hb['shift'])]:
        ct = pd.crosstab(hb.designation, ser); chi, p, _, _ = stats.chi2_contingency(ct); cat.append({'Factor': fac_name, 'Test': 'Chi-square', 'Statistic': f"Cramer's V {np.sqrt(chi / ct.values.sum()):.2f}", 'p': p})
    for x in fam3[:4]: cat.append({'Factor': x[1].split(':')[0], 'Test': 'Fisher exact', 'Statistic': x[3], 'p': x[5]})
    k1, n1, k2, n2 = int(hc.triplet.sum()), len(hc), int(bc.triplet.sum()), len(bc); orr, lo, hi, p = fisher(k1, n1 - k1, k2, n2 - k2); cat.append({'Factor': 'Environmental reading recorded', 'Test': 'Fisher exact', 'Statistic': f'OR {orr:.0f} ({lo:.0f}-{hi:.0f})', 'p': p})
    q = multipletests([r['p'] for r in cat], method='fdr_bh')[1]
    for r, qq in zip(cat, q): r['q (BH, exploratory designation family)'] = f'{qq:.3g}'; r['p'] = f"{r['p']:.3g}"; r['Note'] = 'The primary-family q-value for the worker-context contrasts is in the statistical-tests table (worker-context family)' if r['Test'] == 'Fisher exact' and r['Factor'] != 'Environmental reading recorded' else ''
    pd.DataFrame(cat).to_csv(f'{OUT}/S4b_designation_categorical.csv', index=False); S['S4b'] = cat
    # ---- supplementary S5: co-occurrence
    fac = {f'Inv: {l.split(" (")[0]}': df[f'I::{l}'].astype(int) for l in OPERATIONAL}
    fac.update({'Velocity <0.5 m/s (assessable)': (df.vel < 0.5).astype(int), 'Above or at the statutory limit': (df.env_state == 'Band A or at its limit').astype(int), 'Previous episode': df.prev_episode.eq('Previous episode recorded').astype(int), 'Acute illness': df.acute_illness.eq('Yes or possible').astype(int), 'Alcohol <=48 h or affirmed': df.alcohol.eq('Within 48 h or affirmed').astype(int), 'Medical condition': df.med_condition.eq('Yes').astype(int)})
    Fm = pd.DataFrame(fac); co = []; keys = list(Fm.columns)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            x, y = Fm[keys[i]], Fm[keys[j]]; ct = pd.crosstab(x, y).reindex(index=[0, 1], columns=[0, 1], fill_value=0).values
            phi = (ct[1, 1] * ct[0, 0] - ct[1, 0] * ct[0, 1]) / np.sqrt(max(ct[1].sum() * ct[0].sum() * ct[:, 1].sum() * ct[:, 0].sum(), 1)); _, p = stats.fisher_exact(ct)
            co.append({'Factor 1': keys[i], 'Factor 2': keys[j], 'Both': int(ct[1, 1]), 'Expected both': f'{ct[1].sum() * ct[:, 1].sum() / len(Fm):.1f}', 'phi': f'{phi:.2f}', 'p (Fisher)': p})
    q = multipletests([r['p (Fisher)'] for r in co], method='fdr_bh')[1]
    for r, qq in zip(co, q): r['q (BH)'] = f'{qq:.3g}'; r['p (Fisher)'] = f"{r['p (Fisher)']:.3g}"
    co = sorted(co, key=lambda r: float(r['q (BH)'])); pd.DataFrame(co).to_csv(f'{OUT}/S5_cooccurrence.csv', index=False); S['S5_top'] = co[:6]
    S['monthly'] = monthly.set_index('month').cases.to_dict(); S['n2023'] = int((df.year == 2023).sum()); S['n2024'] = int((df.year == 2024).sum()); S['desig'] = df.designation.value_counts().to_dict(); S['shaft'] = df.shaft.value_counts().to_dict(); S['shift'] = df['shift'].value_counts().to_dict(); S['occ'] = df.occ_group.value_counts().to_dict(); S['season'] = df.season.value_counts().to_dict()
    S['employment'] = df.employment.value_counts().to_dict(); S['generic'] = int(df.occ_generic.sum()); S['complete'] = int(df.complete.sum()); S['triplet'] = int(df.triplet.sum()); S['qc'] = int((df.qc_flag != '').sum()); S['bc_no_triplet'] = int((~bc.triplet).sum()); S['dx_lag_median'] = float(df.dx_lag_days.median())
    S['inv_present'] = int((~df.inv_not_done).sum()); S['complaint_present'] = int(df.complaint_present.sum())
    json.dump(S, open(f'{OUT}/summary.json', 'w'), indent=1, default=str)
    return S

def as_recorded_comparison(SP, SS):
    """SP: summary of the analysis set (cleaned); SS: summary of the register as recorded."""
    comp = []
    def addc(k, vp, vs): comp.append({'Result': k, 'Analysis set (cleaned, n = 178)': vp, 'Register as recorded (n = 179)': vs})
    addc('Cases 2023 / 2024', f"{SP['n2023']} / {SP['n2024']}", f"{SS['n2023']} / {SS['n2024']}")
    for m in ['2023-01', '2023-10', '2024-01', '2024-07', '2024-10']: addc(f'Monthly cases {m}', SP['monthly'].get(m, 0), SS['monthly'].get(m, 0))
    for w in ['Monday', 'Tuesday', 'Wednesday', 'Thursday']: addc(f'Cases on {w}', SP['weekday'][w], SS['weekday'][w])
    addc('Body cramps (n)', SP['desig'].get('Body cramps'), SS['desig'].get('Body cramps')); addc('Quality-valid environmental readings', SP['complete'], SS['complete'])
    addc('Velocity <0.5 m/s among quality-valid readings', SP['env']['v05_ci'], SS['env']['v05_ci'])
    addc('Same-level short-window concentrations (>=3 cases in 3 days)', '; '.join(f"{r['Shaft-level']} {r['Window']} ({r['Cases']})" for r in SP['clusters']), '; '.join(f"{r['Shaft-level']} {r['Window']} ({r['Cases']})" for r in SS['clusters']))
    addc('Previous episode recorded', SP['personal']['prev'], SS['personal']['prev']); addc('Acute illness recorded', SP['personal']['acute'], SS['personal']['acute'])
    addc('Season x designation (supplementary S4, exploratory)', next(r['Statistic'] + ', p = ' + r['p'] for r in SP['S4b'] if r['Factor'] == 'Season'), next(r['Statistic'] + ', p = ' + r['p'] for r in SS['S4b'] if r['Factor'] == 'Season'))
    addc('Monday-Tuesday vs Wednesday-Friday calendar count ratio', f"{SP['robust']['montue_rr'][0]:.2f} ({SP['robust']['montue_rr'][1]:.2f}-{SP['robust']['montue_rr'][2]:.2f})", f"{SS['robust']['montue_rr'][0]:.2f} ({SS['robust']['montue_rr'][1]:.2f}-{SS['robust']['montue_rr'][2]:.2f})")
    addc('Tuesday vs Friday calendar count ratio', f"{SP['poisson']['C(weekday)[T.Tuesday]'][0]:.2f} ({SP['poisson']['C(weekday)[T.Tuesday]'][1]:.2f}-{SP['poisson']['C(weekday)[T.Tuesday]'][2]:.2f})", f"{SS['poisson']['C(weekday)[T.Tuesday]'][0]:.2f} ({SS['poisson']['C(weekday)[T.Tuesday]'][1]:.2f}-{SS['poisson']['C(weekday)[T.Tuesday]'][2]:.2f})")
    addc('A-123 largest 3-day count: P under null A / null B', f"{SP['perm'][0]['P (null A: pooled-calendar re-dating)']} / {SP['perm'][0]['P (null B: exact-date level allocation)']}", f"{SS['perm'][0]['P (null A: pooled-calendar re-dating)']} / {SS['perm'][0]['P (null B: exact-date level allocation)']}")
    pd.DataFrame(comp).to_csv(f'{ROOT}/T14_as_recorded_comparison.csv', index=False); return comp

if __name__ == '__main__':
    os.makedirs(ROOT, exist_ok=True)
    if len(sys.argv) >= 2 and sys.argv[1] == '--from-register':
        stage1(sys.argv[2])
        # the public stage must reproduce from the datasets alone, so run it from the written CSVs
        dfs = {'main': load_dataset(f'{ROOT}/datasets/cases.csv'), 'as_recorded': load_dataset(f'{ROOT}/datasets/cases_as_recorded.csv')}
    elif len(sys.argv) >= 3 and sys.argv[1] == '--from-dataset':
        dfs = {'main': load_dataset(sys.argv[2])}
        if len(sys.argv) >= 4: dfs['as_recorded'] = load_dataset(sys.argv[3])
    else:
        print(__doc__); sys.exit(1)
    SM = analyse(dfs['main'], 'main')
    print(json.dumps({k: SM[k] for k in ['N', 'env', 'robust', 'perm', 'vent_velocity', 't11b', 'neither_ci', 'matches_total']}, indent=1, default=str))
    if 'as_recorded' in dfs:
        SA = analyse(dfs['as_recorded'], 'as_recorded'); comp = as_recorded_comparison(SM, SA)
        print(pd.DataFrame(comp).to_string())
