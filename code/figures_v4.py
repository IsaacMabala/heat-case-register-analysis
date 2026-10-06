"""Figures for the heat-case paper, revision 4 (one cleaned analysis set, adjudicated coding), drawn with larger type.
Every figure is drawn at 7.2 in width (the SAIMM text width is 170 mm = 6.7 in, so the reduction is only 7%) with
tick labels and annotations of 9-10 pt, axis labels of 10 pt and panel titles of 10.5 pt in figure units; Figure 1 is drawn
at 10.1 x 6.35 in for a full landscape page (257 x 170 mm usable), so that it prints at 100%.
Environment: RESULTS_DIR (tables and summary.json), DATASET (the anonymised analysis set), FIG_DIR (output)."""
import pandas as pd, numpy as np, json, os, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import matplotlib.transforms as mtransforms

RES = os.environ.get('RESULTS_DIR', 'results_v4'); OUT = os.environ.get('FIG_DIR', 'figures_v4'); os.makedirs(OUT, exist_ok=True)
c = pd.read_csv(os.environ.get('DATASET', f'{RES}/datasets/cases.csv'), parse_dates=['doa'])
S = json.load(open(f'{RES}/main/summary.json'))
RL = f'{RES}/main/T07b_raise_lines.csv'; PB = S['personal']['by_desig']
N = int(S['N']); NHC = int(S['desig'].get('Heat cramps', 0)); NBC = int(S['desig'].get('Body cramps', 0))
MM = S['mentions']; PCT_VENT = round(100 * MM['Ventilation controls absent or substandard']['I'] / N); PCT_OBS = round(100 * MM['Ore or material accumulation obstructing airflow']['I'] / N)
PCT_PREV = round(100 * S['personal']['prev'] / N); PCT_ACUTE = round(100 * S['personal']['acute'] / N); PCT_ALC = round(100 * S['personal']['alc']['Within 48 h or affirmed'] / N)
MONTUE = S['robust']['montue_rr'][0]

BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
CRIT, WARN = '#d03b3b', '#fab219'
INK, INK2, MUTED, GRID, AXIS, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#ffffff'
NAVY = '#1F3A5F'
# type scale (figure units; the manuscript reduces 7.2 in to 6.7 in)
T_TITLE, T_LABEL, T_TICK, T_ANN, T_NOTE, T_LEG = 10.5, 10, 9.5, 9, 8.5, 9
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': T_LABEL, 'axes.labelsize': T_LABEL, 'xtick.labelsize': T_TICK, 'ytick.labelsize': T_TICK, 'legend.fontsize': T_LEG,
                     'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False, 'figure.dpi': 120, 'savefig.dpi': 300, 'savefig.facecolor': SURF, 'axes.facecolor': SURF})

def style(ax, ygrid=True, xgrid=False):
    if ygrid: ax.yaxis.grid(True, color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    if xgrid: ax.xaxis.grid(True, color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    ax.tick_params(length=0)
    for s in ('left', 'bottom'): ax.spines[s].set_linewidth(0.6)

# ------------------------------------------------------------------ Figure 3: monthly cases by shaft with cluster windows, and the concentrations against chance (replaces the former Table X)
months = pd.period_range('2023-01', '2024-11', freq='M')
mA = c[c.shaft == 'A'].groupby(c.doa.dt.to_period('M')).size().reindex(months, fill_value=0)
mB = c[c.shaft == 'B'].groupby(c.doa.dt.to_period('M')).size().reindex(months, fill_value=0)
fig, (ax, axp) = plt.subplots(2, 1, figsize=(7.2, 7.4), gridspec_kw={'height_ratios': [1.15, 1], 'hspace': 0.5})
x = np.arange(len(months))
ax.bar(x, mA.values, width=0.72, color=BLUE, label='Shaft A', linewidth=0)
ax.bar(x, mB.values, width=0.72, bottom=mA.values, color=ORANGE, label='Shaft B', linewidth=0, edgecolor=SURF)
ax.bar(x, np.where(mB.values > 0, 0.12, 0), width=0.72, bottom=mA.values - 0.06, color=SURF, linewidth=0)
# window annotations are built from the results (summary.json 'clusters'); label offsets per month keep the labels clear of the bars
OFFS = {'2023-10': ((-7.0, 5.6), (1, 0)), '2024-01': ((-8.0, 7.5), (0.5, 0)), '2024-05': ((-6.5, 11.5), (0.5, 0)), '2024-09': ((-8.0, 6.5), (0.5, 0)), '2024-11': ((-4.8, 11.0), (0.5, 0))}
def short_window(w):   # '30 Oct 2023 to 02 Nov 2023' -> '30 Oct–2 Nov'; '13 May 2024 to 14 May 2024' -> '13–14 May'
    a, b = [p.strip().split(' ') for p in w.split(' to ')]
    a_d, a_m = str(int(a[0])), a[1]; b_d, b_m = str(int(b[0])), b[1]
    return f'{a_d}–{b_d} {a_m}' if a_m == b_m else f'{a_d} {a_m}–{b_d} {b_m}'
clusters = {}
for r in S['clusters']:
    m = pd.Timestamp(r['Window'].split(' to ')[0]).to_period('M'); key = str(m)
    txt = f"{r['Shaft-level']}, {short_window(r['Window'])} ({r['Cases']})"
    (dx, dy), rp = OFFS.get(key, ((-6.0, 6.0), (0.5, 0)))
    clusters.setdefault(key, []).append((txt, (dx, dy), rp))
for xi, m in enumerate(months):
    for k, (txt, (dx, dy), rp) in enumerate(clusters.get(str(m), [])):
        tot = mA.values[xi] + mB.values[xi]
        ax.annotate(txt, xy=(xi, tot + 0.2), xytext=(xi + dx, tot + dy + 2.2 * k), fontsize=T_ANN, color=INK2, ha='left', arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.7, shrinkB=1, relpos=rp))
ax.set_xticks(x[::2]); ax.set_xticklabels([m.strftime('%b\n%Y') + ('*' if str(m) in ('2023-01', '2024-11') else '') for m in months[::2]])
ax.set_xlim(-0.7, len(months) + 0.7)
ax.set_ylabel('Recorded cases per month'); ax.set_ylim(0, 29); ax.set_yticks(range(0, 29, 4))
ax.text(len(months) + 0.6, 27.6, '* partial month', ha='right', fontsize=T_NOTE, color=MUTED)
ax.legend(frameon=False, loc='upper left', ncol=2); ax.set_title('(a) Cases per month, with the same-level windows of three or more cases in three days', fontsize=T_TITLE, loc='left', color=INK)
style(ax)
pt = pd.read_csv(f'{RES}/main/T08b_permutation_tests.csv'); pt['lab'] = pt['Shaft-level'].replace({'Any level (maximum over all levels)': 'Any level\n(maximum)'})
xp = np.arange(len(pt)); w = 0.26
axp.bar(xp - w, pt['Null A 95th percentile'], width=w, color='#c9c8c0', linewidth=0, label='Chance, null A (calendar re-dating): 95th percentile')
axp.bar(xp, pt['Null B 95th percentile'], width=w, color='#8d8b84', linewidth=0, label='Chance, null B (exact dates, levels shuffled): 95th percentile')
axp.bar(xp + w, pt['Observed largest 3-day count'], width=w, color=CRIT, linewidth=0, label='Observed largest three-day count')
for i, r in pt.iterrows():
    axp.text(i + w, r['Observed largest 3-day count'] + 0.15, str(int(r['Observed largest 3-day count'])), ha='center', va='bottom', fontsize=T_ANN, color=INK)
    axp.text(i - w, r['Null A 95th percentile'] + 0.15, str(int(r['Null A 95th percentile'])), ha='center', va='bottom', fontsize=T_NOTE, color=INK2)
    axp.text(i, r['Null B 95th percentile'] + 0.15, str(int(r['Null B 95th percentile'])), ha='center', va='bottom', fontsize=T_NOTE, color=INK2)
    pa = r['P (null A: pooled-calendar re-dating)']; pb_ = r['P (null B: exact-date level allocation)']
    fmt = (lambda v: f'{v:.3f}') if pa < 0.1 else (lambda v: f'{v:.2f}')   # each p-value is coloured by its own value
    axp.text(i, 9.15, f'p = {fmt(pa)} (A)', ha='center', va='bottom', fontsize=T_NOTE, color=CRIT if pa < 0.05 else INK2)
    axp.text(i, 8.35, f'p = {fmt(pb_)} (B)', ha='center', va='bottom', fontsize=T_NOTE, color=CRIT if pb_ < 0.05 else INK2)
axp.set_xticks(xp); axp.set_xticklabels([f"{l}\n({int(n)} cases)" for l, n in zip(pt['lab'], pt['Cases'])])
axp.set_ylim(0, 10.6); axp.set_yticks(range(0, 9, 2)); axp.set_ylabel('Cases in three days')
axp.set_title('(b) Is the largest three-day count on a level more than chance would produce?', fontsize=T_TITLE, loc='left', color=INK)
hp, lp = axp.get_legend_handles_labels(); fig.legend(hp, lp, frameon=False, loc='lower center', fontsize=T_NOTE, ncol=1, bbox_to_anchor=(0.5, 0.0))
style(axp)
fig.subplots_adjust(left=0.09, right=0.98, top=0.95, bottom=0.17); fig.savefig(f'{OUT}/Figure_3_monthly_cases_by_shaft.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 1: wet-bulb vs air velocity, drawn for a full landscape page (10.1 x 6.35 in; SAIMM A4 with 20 mm margins is 257 x 170 mm)
# with the marginal distributions, the band-by-velocity counts (the former Table III) and a key in a right-hand column outside the data area
# data ---------------------------------------------------------------------------------------------------------------
a = c[c.complete].copy()
rng = np.random.default_rng(7)
a['vj'] = a.vel + rng.uniform(-0.015, 0.015, len(a)); a['wj'] = a.wb + rng.uniform(-0.08, 0.08, len(a))
t3 = pd.read_csv(f'{RES}/main/T03_band_by_velocity.csv')
nA, nB, nC, nD = [int(str(t3.iloc[i, 1]).split('/')[0]) for i in range(4)]
vcls = [int((a.vel < 0.25).sum()), int(((a.vel >= 0.25) & (a.vel < 0.5)).sum()), int(((a.vel >= 0.5) & (a.vel < 1.0)).sum()), int((a.vel >= 1.0).sum())]
YLO, YHI, XLO, XHI = 25.4, 38.2, -0.05, 3.5
PINK, PEACH, GREY = '#fbe9e9', '#fdf1ea', '#f1f1ec'
DASH, DOT = (0, (4, 3)), (0, (2, 3))

# layout -------------------------------------------------------------------------------------------------------------
fig = plt.figure(figsize=(10.1, 6.35))
ax = fig.add_axes([0.06, 0.105, 0.47, 0.625])
axt = fig.add_axes([0.06, 0.755, 0.47, 0.18])
axr = fig.add_axes([0.548, 0.105, 0.09, 0.625])
axtab = fig.add_axes([0.685, 0.755, 0.305, 0.18]); axtab.axis('off')
axk = fig.add_axes([0.685, 0.04, 0.305, 0.69]); axk.axis('off'); axk.set_xlim(0, 1); axk.set_ylim(0, 1)

# scatter panel ------------------------------------------------------------------------------------------------------
ax.axhspan(27.5, 32.5, color=GREY, zorder=0); ax.axvspan(XLO, 0.5, color=PEACH, zorder=0, alpha=0.9); ax.axhspan(32.5, YHI, color=PINK, zorder=0)
ax.axhline(29.0, color=MUTED, linewidth=0.8, linestyle=DOT); ax.axhline(27.5, color=MUTED, linewidth=0.9, linestyle=DASH); ax.axhline(32.5, color=CRIT, linewidth=0.9, linestyle=DASH)
ax.axvline(1.0, color=MUTED, linewidth=0.8, linestyle=DOT); ax.axvline(0.5, color=WARN, linewidth=0.9, linestyle=DASH); ax.axvline(0.25, color=CRIT, linewidth=0.9, linestyle=DASH)
MARK = [('Heat cramps', BLUE, 'o', 3), ('Body cramps', ORANGE, 's', 4), ('Heat stroke', CRIT, '^', 5), ('Unclassified', MUTED, 'D', 4)]
for lab, col, mk, z in MARK:
    s_ = a[a.designation == lab]; ax.scatter(s_.vj, s_.wj, s=40, marker=mk, color=col, edgecolor=SURF, linewidth=0.8, zorder=z)
db37 = a[a.db >= 37]; ax.scatter(db37.vj, db37.wj, s=150, facecolor='none', edgecolor=CRIT, linewidth=1.1, zorder=6)
for yv, txt in [(33.35, f'Band A  (wet-bulb >32.5 °C): {nA} readings'), (32.05, f'Band B  (>29.0 to 32.5 °C): {nB} readings'), (28.55, f'Band C  (>27.5 to 29.0 °C): {nC} readings'), (25.85, f'Band D  (≤27.5 °C): {nD} readings')]:
    ax.text(3.45, yv, txt, ha='right', va='center', fontsize=T_ANN, color=INK2, zorder=7)
ax.set_xlabel('Air velocity at the recorded reading (m/s)'); ax.set_ylabel('Wet-bulb temperature at the recorded reading (°C)')
ax.set_xlim(XLO, XHI); ax.set_ylim(YLO, YHI); ax.set_yticks(range(26, 39, 2)); ax.set_xticks(np.arange(0, 3.01, 0.5))
style(ax, ygrid=True)

# top marginal: air velocity -----------------------------------------------------------------------------------------
bins = np.arange(0, 3.55, 0.1); axt.hist(a.vel, bins=bins, color='#9dbfe8', edgecolor=SURF, linewidth=0.5)
for xv, col, ls in ((0.25, CRIT, DASH), (0.5, WARN, DASH), (1.0, MUTED, DOT)): axt.axvline(xv, color=col, linewidth=0.9, linestyle=ls)
axt.set_xlim(XLO, XHI); axt.set_ylim(0, 27); axt.set_yticks([0, 10, 20]); axt.tick_params(labelbottom=False); axt.set_ylabel('Readings', fontsize=T_NOTE)
axt.set_title('Air velocity: readings per 0.1 m/s', fontsize=T_ANN, loc='left', color=INK)
style(axt)

# right marginal: wet-bulb -------------------------------------------------------------------------------------------
binsy = np.arange(25, 40.5, 0.5); axr.hist(a.wb, bins=binsy, orientation='horizontal', color='#9dbfe8', edgecolor=SURF, linewidth=0.5)
for yv, col, ls in ((27.5, MUTED, DASH), (29.0, MUTED, DOT), (32.5, CRIT, DASH)): axr.axhline(yv, color=col, linewidth=0.9, linestyle=ls)
axr.set_ylim(YLO, YHI); axr.set_xlim(0, 32); axr.set_xticks([0, 15, 30]); axr.tick_params(labelleft=False); axr.set_xlabel('Readings', fontsize=T_NOTE)
axr.set_title('Wet-bulb:\nreadings per 0.5 °C', fontsize=T_ANN, loc='left', color=INK); style(axr, ygrid=False, xgrid=True)

# table: band by velocity class (the former Table III) ---------------------------------------------------------------
rows = []
for i in range(4):
    r = t3.iloc[i]; rows.append([r.iloc[0].replace('Band ', ''), f'{int(r.iloc[2])}', f'{int(r.iloc[3])}', f'{int(r.iloc[4])}', f'{int(r.iloc[5])}', str(r.iloc[1]).split('/')[0]])
rows.append(['All', *[str(v) for v in vcls], str(sum(vcls))])
tb = axtab.table(cellText=rows, colLabels=['Band', '<0.25\nm/s', '0.25–\n<0.5', '0.5–\n<1.0', '≥1.0\nm/s', 'All'], loc='center', cellLoc='center', colLoc='center', bbox=[0.0, 0.0, 1.0, 0.86])
tb.auto_set_font_size(False); tb.set_fontsize(T_NOTE)
for (r_, c_), cell in tb.get_celld().items():
    cell.set_edgecolor(GRID); cell.set_linewidth(0.5)
    if r_ == 0: cell.set_text_props(fontweight='bold', color=INK); cell.set_facecolor('#f3f2ee'); cell.set_height(cell.get_height() * 1.6)
    if r_ == 5: cell.set_text_props(fontweight='bold', color=INK)
axtab.text(0.0, 0.97, 'Readings by band and velocity class', fontsize=T_ANN, color=INK, va='bottom', fontweight='bold')

# key ----------------------------------------------------------------------------------------------------------------
R1, R2, HG = 0.044, 0.076, 0.03   # single-line row, two-line row, extra gap before a heading (axes fraction)
state = {'y': 1.0, 'h': 0.0}
def step(h):
    state['y'] -= (state['h'] + h) / 2; state['h'] = h; return state['y']
def head(txt):
    y = step(R1) - HG; state['y'] = y; axk.text(0.0, y, txt, fontsize=T_NOTE, color=INK, fontweight='bold', va='center')
def row(txt, draw):
    y = step(R2 if '\n' in txt else R1); draw(y); axk.text(0.115, y, txt, fontsize=T_NOTE, color=INK2, va='center', linespacing=1.1)
state['h'] = -R1 + 0.03; head('CASES (one spot reading per case)')
for lab, col, mk, _ in MARK:
    row(f'{lab} (n = {int((a.designation == lab).sum())})', lambda y, col=col, mk=mk: axk.scatter([0.045], [y], s=40, marker=mk, color=col, edgecolor=SURF, linewidth=0.8, clip_on=False))
row(f'Dry-bulb 37 °C, the statutory limit (n = {len(db37)})', lambda y: axk.scatter([0.045], [y], s=150, facecolor='none', edgecolor=CRIT, linewidth=1.1, clip_on=False))
head('REFERENCE LINES')
for col, ls, txt, vert in ((CRIT, DASH, '32.5 °C: statutory limit; Band A above it', False), (MUTED, DOT, '29.0 °C: Band B / Band C boundary', False), (MUTED, DASH, '27.5 °C: Band C / Band D boundary', False),
                          (CRIT, DASH, '0.25 m/s: lower literature reference\n(gas dilution; non-statutory)', True), (WARN, DASH, '0.5 m/s: principal analytical screen\n(provisional)', True), (MUTED, DOT, '1.0 m/s: upper sensitivity screen', True)):
    if vert: row(txt, lambda y, col=col, ls=ls: axk.plot([0.045, 0.045], [y - 0.024, y + 0.024], color=col, linewidth=1.1, linestyle=ls, clip_on=False))
    else: row(txt, lambda y, col=col, ls=ls: axk.plot([0.005, 0.085], [y, y], color=col, linewidth=1.1, linestyle=ls, clip_on=False))
head('SHADED AREAS')
for col, txt in ((PINK, 'Band A range: above the statutory limit'), (PEACH, 'Velocity below the 0.5 m/s screen'), (GREY, 'Band B or C with velocity ≥0.5 m/s:\nwithin the review screen')):
    row(txt, lambda y, col=col: axk.add_patch(Rectangle((0.005, y - 0.019), 0.08, 0.038, facecolor=col, edgecolor=AXIS, linewidth=0.5, clip_on=False)))
y = step(R1) - 0.02
axk.text(0.0, y, 'Velocity screens are analytical values, not statutory\nminima. Points are offset slightly to separate\nidentical readings.', fontsize=T_NOTE - 0.5, color=MUTED, va='top', linespacing=1.2)
fig.savefig(f'{OUT}/Figure_1_wetbulb_velocity_state.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 4: raise-line recurrence (bars plus aligned text columns; replaces the former Table VIII)
rl = pd.read_csv(RL).head(12)
fig, ax = plt.subplots(figsize=(7.2, 4.8))
y = np.arange(len(rl))[::-1]
cols = [BLUE if s_ == 'A' else ORANGE for s_ in rl.shaft]
ax.barh(y, rl.cases, height=0.62, color=cols, linewidth=0)
for yi, n in zip(y, rl.cases): ax.text(n + 0.15, yi, str(n), va='center', fontsize=T_ANN, color=INK2)
ax.set_yticks(y); ax.set_yticklabels(rl.raise_code)
ax.set_xlabel('Recorded cases, Jan 2023 to Nov 2024'); ax.set_xlim(0, 12.5); ax.set_xticks(range(0, 13, 4))
ax.set_ylim(-0.7, len(rl) - 0.3)
style(ax, ygrid=False, xgrid=True)
fig.subplots_adjust(left=0.10, right=0.44, top=0.84, bottom=0.12)
tr = mtransforms.blended_transform_factory(fig.transFigure, ax.transData)
colx = [0.505, 0.605, 0.705, 0.805, 0.92]; heads = ['Ventilation\ncontrols', 'Obstruction', 'Local\ncooling', 'Mine-level\nrefrigeration', 'Velocity\n<0.5 m/s']
for cx, hd in zip(colx, heads): fig.text(cx, len(rl) - 0.15, hd, ha='center', va='bottom', fontsize=8.2, color=INK, fontweight='bold', transform=tr, linespacing=1.15)
for yi, (vc, ob, lc, mr, assess, vd) in zip(y, zip(rl.vent_controls, rl.obstruction, rl.local_cooling, rl.mine_refrig, rl.assessable, rl.vel_deficient)):
    for cx, v in zip(colx, [str(vc), str(ob), str(lc), str(mr), f'{vd}/{assess}']): fig.text(cx, yi, v, ha='center', va='center', fontsize=T_ANN, color=INK2, transform=tr)
fig.text(0.985, len(rl) + 1.25, 'Cases whose investigation carries the adjudicated statement; readings below 0.5 m/s / assessable', ha='right', va='bottom', fontsize=T_NOTE, color=INK2, transform=tr)
ax.legend(handles=[Line2D([0], [0], color=BLUE, lw=7), Line2D([0], [0], color=ORANGE, lw=7)], labels=['Shaft A', 'Shaft B'], frameon=False, loc='lower right', ncol=1)
fig.savefig(f'{OUT}/Figure_4_raise_line_recurrence.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 2: weekday profile (replaces the former Tables VI and VII)
wk = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
hc = c[c.designation == 'Heat cramps'].weekday.value_counts().reindex(wk, fill_value=0)
bc = c[c.designation == 'Body cramps'].weekday.value_counts().reindex(wk, fill_value=0)
oth = c[~c.designation.isin(['Heat cramps', 'Body cramps'])].weekday.value_counts().reindex(wk, fill_value=0)
alc = pd.Series(S['alc_by_weekday']).reindex(wk); tot = c.weekday.value_counts().reindex(wk, fill_value=0)
fig, axs = plt.subplots(2, 2, figsize=(7.2, 6.8), gridspec_kw={'width_ratios': [1.2, 1], 'hspace': 0.42, 'wspace': 0.45})
ax1, ax2, ax3, ax4 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]
x = np.arange(7)
ax1.bar(x, hc, width=0.7, color=BLUE, label='Heat cramps', linewidth=0)
ax1.bar(x, bc, width=0.7, bottom=hc + 0.15, color=ORANGE, label='Body cramps', linewidth=0)
ax1.bar(x, oth, width=0.7, bottom=hc + bc + 0.3, color=MUTED, label='Other', linewidth=0)
for xi, t in enumerate(tot): ax1.text(xi, t + 1.0, str(t), ha='center', fontsize=T_ANN, color=INK2)
ax1.set_xticks(x); ax1.set_xticklabels([w[:3] for w in wk]); ax1.set_ylabel('Recorded cases'); ax1.set_ylim(0, 82)
ax1.legend(frameon=False, loc='upper right'); ax1.set_title('(a) Cases by weekday of the case date', fontsize=T_TITLE, loc='left', color=INK)
style(ax1)
share = (alc / tot * 100).fillna(0)
ax2.bar(x, share, width=0.7, color=WARN, linewidth=0)
for xi, (s_, n_, t_) in enumerate(zip(share, alc, tot)):
    if t_ > 0: ax2.text(xi, s_ + 1.2, f'{int(n_)}/{int(t_)}', ha='center', fontsize=T_ANN, color=INK2)
ax2.set_xticks(x); ax2.set_xticklabels([w[:3] for w in wk]); ax2.set_ylabel('Alcohol ≤48 h or affirmed\n(% of cases)'); ax2.set_ylim(0, 40)
ax2.set_title('(b) Alcohol documented ≤48 h', fontsize=T_TITLE, loc='left', color=INK)
style(ax2)
# (c) calendar count ratios vs Friday (Poisson model) and the grouped contrast with its bootstrap interval
pm = pd.read_csv(f'{RES}/main/T06e_poisson_calendar_model.csv').set_index('term')
rb = pd.read_csv(f'{RES}/main/T06f_weekday_model_robustness.csv').set_index('Contrast')
rows = [(f'C(weekday)[T.{d}]', d) for d in ('Monday', 'Tuesday', 'Wednesday', 'Thursday')]
labels_c, est, lo, hi = [], [], [], []
for term, d in rows: labels_c.append(f'{d[:3]} vs Fri'); est.append(pm.loc[term, 'rate_ratio']); lo.append(pm.loc[term, 'ci_low']); hi.append(pm.loc[term, 'ci_high'])
g = rb.loc['Monday-Tuesday vs Wednesday-Friday (grouped model)']; gp = g.iloc[0]; gb = g.iloc[3]
g_est = float(gp.split(' ')[0]); g_lo, g_hi = [float(v) for v in gp.split('(')[1].rstrip(')').split('-')]; b_lo, b_hi = [float(v) for v in gb.split('-')]
labels_c.append('Mon–Tue vs\nWed–Fri'); est.append(g_est); lo.append(g_lo); hi.append(g_hi)
yc = np.arange(len(labels_c))[::-1]
ax3.axvline(1, color=MUTED, linewidth=0.8)
ax3.hlines(yc[-1] - 0.22, b_lo, b_hi, color=MUTED, linewidth=2.2, label='Week-block bootstrap interval')
ax3.errorbar(est, yc, xerr=[np.array(est) - np.array(lo), np.array(hi) - np.array(est)], fmt='o', color=BLUE, ecolor=BLUE, elinewidth=1.4, capsize=3, markersize=6, label='Poisson calendar model, 95% CI')
for yi, e, h in zip(yc, est, hi): ax3.text(h * 1.12, yi, f'{e:.1f}', va='center', fontsize=T_ANN, color=INK2)
ax3.set_xscale('log'); ax3.set_xlim(0.5, 30); ax3.set_xticks([0.5, 1, 2, 5, 10, 20]); ax3.set_xticklabels(['0.5', '1', '2', '5', '10', '20'])
ax3.set_yticks(yc); ax3.set_yticklabels(labels_c); ax3.set_xlabel('Calendar count ratio (1 = no difference)')
ax3.set_title('(c) Calendar count ratios', fontsize=T_TITLE, loc='left', color=INK); ax3.set_ylim(-0.7, len(labels_c) - 0.4)
style(ax3, ygrid=False, xgrid=True)
# (d) readings below 0.5 m/s by weekday
wt = pd.read_csv(f'{RES}/main/T06_weekday.csv'); vd = wt['Velocity <0.5 m/s / assessable'].str.split('/', expand=True).astype(int)
num, den = vd[0].values, vd[1].values; shr = np.where(den > 0, 100 * num / np.maximum(den, 1), 0)
ax4.bar(x, shr, width=0.7, color=CRIT, linewidth=0)
for xi, (n_, d_) in enumerate(zip(num, den)):
    if d_ > 0: ax4.text(xi, shr[xi] + 1.2, f'{n_}/{d_}', ha='center', fontsize=T_ANN, color=INK2)
ax4.set_xticks(x); ax4.set_xticklabels([w[:3] for w in wk]); ax4.set_ylabel('Readings <0.5 m/s\n(% of assessable)'); ax4.set_ylim(0, 45)
ax4.set_title('(d) Readings below 0.5 m/s', fontsize=T_TITLE, loc='left', color=INK)
style(ax4)
h3, l3 = ax3.get_legend_handles_labels(); fig.legend(h3, l3, frameon=False, loc='lower center', ncol=2, fontsize=T_NOTE, bbox_to_anchor=(0.5, 0.005))
fig.subplots_adjust(left=0.14, right=0.98, top=0.955, bottom=0.13); fig.savefig(f'{OUT}/Figure_2_weekday_profile.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 6: worker-context indicators by designation (replaces the former Table XII)
pb = PB
WCI_MASK = (c.prev_episode == 'Previous episode recorded') | (c.acute_illness == 'Yes or possible') | (c.alcohol == 'Within 48 h or affirmed') | (c.med_control == 'Poorly or partly controlled')
anyhc = int(WCI_MASK[c.designation == 'Heat cramps'].sum()); anybc = int(WCI_MASK[c.designation == 'Body cramps'].sum())
labels = ['Any recorded indicator', 'Previous episode recorded', 'Acute illness at the time', 'Alcohol documented ≤48 h or affirmed', 'Medical condition recorded', 'Condition poorly or partly controlled']
hcn = [anyhc, pb['Heat cramps']['prev'], pb['Heat cramps']['acute'], pb['Heat cramps']['alc48'], pb['Heat cramps']['medyes'], pb['Heat cramps']['medpoor']]
bcn = [anybc, pb['Body cramps']['prev'], pb['Body cramps']['acute'], pb['Body cramps']['alc48'], pb['Body cramps']['medyes'], pb['Body cramps']['medpoor']]
nh, nb = pb['Heat cramps']['n'], pb['Body cramps']['n']
hcv = [100 * v / nh for v in hcn]; bcv = [100 * v / nb for v in bcn]
fig, ax = plt.subplots(figsize=(7.2, 4.5))
y = np.arange(len(labels))[::-1]; h = 0.34
ax.barh(y + h / 2 + 0.02, hcv, height=h, color=BLUE, label=f'Heat cramps (n = {nh})', linewidth=0)
ax.barh(y - h / 2 - 0.02, bcv, height=h, color=ORANGE, label=f'Body cramps (n = {nb})', linewidth=0)
for yi, hn, hv, bn, bv in zip(y, hcn, hcv, bcn, bcv):
    ax.text(hv + 0.6, yi + h / 2 + 0.02, f'{hn} ({hv:.0f}%)', va='center', fontsize=T_ANN, color=INK2)
    ax.text(bv + 0.6, yi - h / 2 - 0.02, f'{bn} ({bv:.0f}%)', va='center', fontsize=T_ANN, color=INK2)
ax.set_yticks(y); ax.set_yticklabels(labels); ax.set_xlabel('Share of recorded cases (%)'); ax.set_xlim(0, 70); ax.set_ylim(-1.35, len(labels) - 0.4)
ax.legend(frameon=False, loc='lower right', bbox_to_anchor=(1.0, 1.0), ncol=2)
ax.text(0, -0.95, f"Heat-tolerance screening date within 12 months: {S['hts']['le12']} of {S['hts']['valid']} cases", ha='left', va='center', fontsize=T_NOTE, color=INK2)
style(ax, ygrid=False, xgrid=True)
fig.tight_layout(); fig.savefig(f'{OUT}/Figure_6_worker_context_by_designation.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 5: coded statements by source, with the designation split and the velocity readings (replaces the former Table XI)
M = S['mentions']; labels = list(M.keys())
order = sorted(labels, key=lambda k: -M[k]['either'])
t9 = pd.read_csv(f'{RES}/main/T09_documentary_mentions.csv'); t9 = t9.set_index(t9.columns[0])
fig, ax = plt.subplots(figsize=(7.2, 6.4))
y = np.arange(len(order))[::-1]; h = 0.36
ax.barh(y + h / 2 + 0.02, [M[k]['I'] for k in order], height=h, color=BLUE, label='Investigation text', linewidth=0)
ax.barh(y - h / 2 - 0.02, [M[k]['C'] for k in order], height=h, color=ORANGE, label='Employee complaint text', linewidth=0)
for yi, k in zip(y, order):
    ax.text(M[k]['I'] + 0.8, yi + h / 2 + 0.02, str(M[k]['I']), va='center', fontsize=T_ANN, color=INK2)
    ax.text(M[k]['C'] + 0.8, yi - h / 2 - 0.02, str(M[k]['C']), va='center', fontsize=T_ANN, color=INK2)
short5 = {'Mine-level refrigeration (fridge plant, bulk air cooler, chilled water)': 'Mine-level refrigeration\n(fridge plant, BAC, chilled water)',
          'Local cooling equipment (cooling car, in-stope cooler)': 'Local cooling equipment\n(cooling car, in-stope cooler)',
          'Work organisation (staff shortage, overtime, long shift, extra task)': 'Work organisation (staff\nshortage, overtime, long shift)',
          'Entry examination, temperature measurement or supervision not done': 'Entry examination,\ntemperature check or\nsupervision not done',
          'Ventilation controls absent or substandard': 'Ventilation controls\nabsent or substandard', 'Ore or material accumulation obstructing airflow': 'Ore or material accumulation\nobstructing airflow',
          'Fan not operating, not installed or obstructed': 'Fan not operating, not\ninstalled or obstructed', 'Ventilation column or duct leakage or distance': 'Ventilation column or duct\nleakage or distance',
          'Complaint not acted on or hazard known': 'Complaint not acted on\nor hazard known', 'Water, wet conditions or fissure heat': 'Water, wet conditions\nor fissure heat', 'No substandard condition identified': 'No substandard\ncondition identified'}
ax.set_yticks(y); ax.set_yticklabels([short5.get(k, k) for k in order])
ax.set_xlabel(f'Records carrying the statement (n = {N})'); ax.set_xlim(0, 80); ax.set_xticks(range(0, 81, 20)); ax.set_ylim(-0.7, len(order) - 0.3)
style(ax, ygrid=False, xgrid=True)
fig.subplots_adjust(left=0.32, right=0.655, top=0.86, bottom=0.14)
h5, l5 = ax.get_legend_handles_labels(); fig.legend(h5, l5, frameon=False, loc='lower center', ncol=2, bbox_to_anchor=(0.5, 0.005))
tr = mtransforms.blended_transform_factory(fig.transFigure, ax.transData)
colx = [0.725, 0.835, 0.945]; heads = [f'Heat cramps\n(n = {NHC})', f'Body cramps\n(n = {NBC})', '<0.5 m/s /\nassessable']
for cx, hd in zip(colx, heads): fig.text(cx, len(order) - 0.15, hd, ha='center', va='bottom', fontsize=7.6, color=INK, fontweight='bold', transform=tr, linespacing=1.15)
for yi, k in zip(y, order):
    r = t9.loc[k]; vals = [str(r['Heat cramps (either)']).split(' ')[0], str(r['Body cramps (either)']).split(' ')[0], str(r['Velocity <0.5 m/s / assessable (investigation-coded)'])]
    for cx, v in zip(colx, vals): fig.text(cx, yi, v, ha='center', va='center', fontsize=T_ANN, color=INK2, transform=tr)
fig.text(0.985, len(order) + 1.35, 'Records from either source, by designation; readings below 0.5 m/s among investigation-coded records', ha='right', va='bottom', fontsize=T_NOTE, color=INK2, transform=tr)
fig.savefig(f'{OUT}/Figure_5_coded_statements.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 7: CRA integration diagram
fig, ax = plt.subplots(figsize=(7.2, 6.1)); ax.set_xlim(0, 100); ax.set_ylim(5.5, 100); ax.axis('off')
def box(x, y, w, h, title, body, fc, tc=INK, tfs=9.2, bfs=8.4, ls=1.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=1.2', facecolor=fc, edgecolor='none'))
    ax.text(x + 1.4, y + h - 1.2, title, fontsize=tfs, fontweight='bold', va='top', color=tc)
    ax.text(x + 1.4, y + h - 5.2, body, fontsize=bfs, va='top', color=tc, linespacing=ls)
cols4 = ['#e3ecf9', '#fdeae2', '#e2f5ee', '#f3f2ee']
lenses = [('PLACE', 'Raise lines and sections\nwith recurrent cases;\nthe upstream\nrefrigeration district'),
          ('TIME', f'Monday–Tuesday\nconcentration ({MONTUE:.1f}× the\nWed–Fri calendar rate);\nsame-level short-window\nconcentrations'),
          ('CONTROL', f'Ventilation-control\nstatements in {PCT_VENT}% of\nrecords; obstruction {PCT_OBS}%;\ncooling car, fridge plant,\nBAC; water (adjudicated)'),
          ('WORKER CONTEXT', f'Previous episode ({PCT_PREV}%);\nacute illness ({PCT_ACUTE}%);\nalcohol documented ≤48 h\nor affirmed ({PCT_ALC}%);\nscreening interval')]
YS = [79, 59.5, 40, 20.5]; H = 18
for i, (t, b) in enumerate(lenses):
    box(1, YS[i], 25, H, t, b, cols4[i])
trig = [('Pre-entry declaration · COP action', 'Wet-bulb, dry-bulb and velocity at the face\nbefore entry; readings at or above the\nstatutory limit → verification and COP\naction; velocity below the mine-approved\nthreshold escalated'),
        ('Graded triggers · proposed', 'Two cases on one level within 48 h, or a\nsecond case on a raise line within 30 days\n→ management review; three cases on a level\nwithin three days, or a concern confirmed on\ninspection → section 11 issue-based\nassessment; no automatic withdrawal'),
        ('Control verification · review', 'Coded control concern → prompt inspection;\ndeficiency confirmed → corrective action\nand sign-off; fridge plant, BAC and\ncooling-car status checked against the\nshift plan'),
        ('Fitness for work · medical', 'Return after an episode, illness or leave\nassessed by the occupational health centre;\nalcohol history handled clinically, not as\na supervisory trigger')]
for i, (t, b) in enumerate(trig):
    box(30.5, YS[i], 39.5, H, t, b, '#f7f7f4', bfs=8.0 if i == 1 else 8.4, ls=1.22 if i == 1 else 1.3)
    ax.add_patch(FancyArrowPatch((26.6, YS[i] + H / 2), (29.9, YS[i] + H / 2), arrowstyle='-|>', mutation_scale=9, color=MUTED, lw=0.9))
    ax.add_patch(FancyArrowPatch((70.6, YS[i] + H / 2), (73.9, YS[i] + H / 2), arrowstyle='-|>', mutation_scale=9, color=MUTED, lw=0.9))
box(74.5, 20.5, 24.5, 76.5, 'CLOSE THE LOOP', 'Owner and due time\nrecorded\n\nMeasurement repeated\nafter the control is\nrestored, not before\n\nComplaint-to-measurement\nlatency tracked per\nsection\n\nInvestigation completed\nfor every designation,\nincluding body cramps\n\nMonthly profile review by\nthe OHE and ventilation\nmanager\n\nMINIMUM RECORD\nTime of onset and of\nreading; instrument;\nposition; control state\nbefore and after; shaft,\nlevel, raise, panel and\nsection; designation\nreason, occupation and\nstatement classes from\ncontrolled lists', '#f7f7f4', bfs=7.8, ls=1.18)
ax.text(1, 16.5, 'Reference values: statutory limits WB 32.5 °C / DB 37 °C (MHSA Schedule 22.9); the regulator’s Bands A–D\napplied as numerical ranges. Velocity screens (0.25, 0.5, 1.0 m/s) are analytical values, not statutory minima.\nAll numerical triggers are proposed values to be confirmed within the mine’s mandatory code of practice;\nthe worker-context indicators are governed clinically by the occupational health centre.', fontsize=T_NOTE, color=MUTED, va='top', linespacing=1.35)
fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01); fig.savefig(f'{OUT}/Figure_7_CRA_integration.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 8: hybrid monitoring architecture
fig, ax = plt.subplots(figsize=(7.2, 5.6)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')
layers = [('GOVERNANCE AND REGULATORY CONTROL', 'MHSA and mine codes of practice · roles and competence · access · retention ·\napproved rules · audit', '#1F3A5F'),
          ('SENSE AND OBSERVE', 'Fixed or relocatable sensors · portable instruments · physical inspections ·\ncomplaints and investigations against controlled lists · control telemetry', '#2a78d6'),
          ('CONTEXTUALISE AND INTEGRATE', 'Synchronised time · location master (shaft, level, raise, panel, section) ·\nHEG and occupancy · task and duration', '#1baf7a'),
          ('QUALITY-ASSURE AND VALIDATE', 'Instrument identity · calibration · field checks · uncertainty ·\nrepresentativeness · sign-off · traceability', '#eb6834'),
          ('ASSESS AND DECIDE', 'COP rules · CRA triggers · trends · recurrence by raise line and level ·\nanomaly detection · interpretation', '#4a8f3f'),
          ('ACT, VERIFY AND LEARN', 'Engineering response · acknowledgement · owner and due time ·\npost-control measurement · close-out · review', '#d03b3b')]
for i, (t, b, col) in enumerate(layers):
    y = 86 - i * 15.2
    ax.add_patch(FancyBboxPatch((9, y), 82, 12.6, boxstyle='round,pad=0.3,rounding_size=1.0', facecolor=col, edgecolor='none'))
    ax.text(11, y + 10.3, t, fontsize=9.5, fontweight='bold', color='white', va='center')
    ax.text(11, y + 4.6, b, fontsize=8.4, color='white', va='center', linespacing=1.3)
    if i < 5: ax.add_patch(FancyArrowPatch((50, y - 0.2), (50, y - 2.4), arrowstyle='-|>', mutation_scale=8, color=INK2, lw=0.9))
ax.add_patch(FancyArrowPatch((5.0, 11), (5.0, 86), arrowstyle='-|>', mutation_scale=8, color=BLUE, lw=1.1)); ax.text(2.2, 50, 'Manual fallback and verification', rotation=90, va='center', ha='center', fontsize=T_NOTE, color=BLUE)
ax.add_patch(FancyArrowPatch((95.0, 11), (95.0, 86), arrowstyle='-|>', mutation_scale=8, color=CRIT, lw=1.1)); ax.text(97.8, 50, 'Feedback and change control', rotation=90, va='center', ha='center', fontsize=T_NOTE, color=CRIT)
ax.text(50, 3.0, 'A dashboard is a governed view of validated evidence, not a substitute for representative\nmeasurement, inspection or competent judgement.', ha='center', fontsize=T_NOTE, color=MUTED, linespacing=1.3)
fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01); fig.savefig(f'{OUT}/Figure_8_hybrid_architecture.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 9: historical dashboard populated from the analysis set (portrait, explicit layout)
E = S['env']; M = S['mentions']; P = S['personal']; W = S['weekday']; ALC = S['alc_by_weekday']
FS = 9
fig = plt.figure(figsize=(7.2, 10.0))
fig.text(0.02, 0.978, 'Historical heat-case evidence dashboard', fontsize=14, fontweight='bold', color=INK, ha='left', va='top')
fig.text(0.02, 0.953, f'Cleaned analysis set (n = {N}; one duplicate removed, four dates corrected), {c.doa.min():%d %B %Y} to {c.doa.max():%d %B %Y}.\nDescribes recorded cases and adjudicated coded statements, not incidence, compliance\nor prospective risk.', fontsize=FS - 0.5, color=INK2, ha='left', va='top', linespacing=1.35)
kpis = [('CASES ANALYSED', f'{N}', f"Shaft A {S['shaft'].get('A', 0)} · Shaft B {S['shaft'].get('B', 0)}", BLUE), ('QUALITY-VALID READINGS', f"{E['assessable']} ({E['assessable'] / N:.0%})", f"{S['qc']} flagged · {N - S['triplet']} no reading", AQUA),
        ('INVESTIGATION PRESENT', f"{S['inv_present']} ({S['inv_present'] / N:.0%})", f"{S['inv_not_done']} without · {S['inv_not_done_bc']} body-cramp", ORANGE), ('FLAGGED BY SCREEN', f"{E['review']}/{E['assessable']} ({E['review'] / E['assessable']:.0%})", f"≥limit {E['states']['Band A or at its limit']} · <0.5 m/s {E['review'] - E['states']['Band A or at its limit']}", CRIT)]
axk = fig.add_axes([0.02, 0.815, 0.96, 0.075]); axk.set_xlim(0, 4); axk.set_ylim(0, 1); axk.axis('off')
for i, (lab, val, sub, col) in enumerate(kpis):
    axk.add_patch(Rectangle((i + 0.02, 0.0), 0.96, 1.0, facecolor='#f6f5f1', edgecolor='none')); axk.add_patch(Rectangle((i + 0.02, 0.9), 0.96, 0.1, facecolor=col, edgecolor='none'))
    axk.text(i + 0.06, 0.70, lab, fontsize=7.2, color=INK2); axk.text(i + 0.06, 0.33, val, fontsize=12.5, fontweight='bold', color=INK); axk.text(i + 0.06, 0.08, sub, fontsize=7.2, color=MUTED)
ROWS = [0.585, 0.335, 0.085]; PH = 0.175; LX, RX, PW = 0.215, 0.715, 0.265
def dpanel(row, col, title):
    axp = fig.add_axes([LX if col == 0 else RX, ROWS[row], PW, PH]); axp.set_title(title, fontsize=FS + 1, loc='left', color=INK, pad=6); axp.tick_params(labelsize=FS); return axp
ax = dpanel(0, 0, 'Monthly cases by shaft (▲ 3-day window)'); x = np.arange(len(months))
ax.bar(x, mA.values, width=0.75, color=BLUE, label='Shaft A', linewidth=0); ax.bar(x, mB.values, width=0.75, bottom=mA.values, color=ORANGE, label='Shaft B', linewidth=0)
for xi, m in enumerate(months):
    if str(m) in clusters: ax.text(xi, mA.values[xi] + mB.values[xi] + 0.4, '▲', ha='center', fontsize=8, color=CRIT)
ax.set_xticks(x[::6]); ax.set_xticklabels([m.strftime('%b\n%Y') for m in months][::6]); ax.set_ylim(0, 24); ax.legend(frameon=False, fontsize=FS - 0.5, loc='upper left'); style(ax)
ax = dpanel(0, 1, f'Cases by weekday\n(Mon–Tue vs Wed–Fri: {MONTUE:.1f}×)'); days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']; vals = [W[d] for d in days]; alc = [ALC[d] for d in days]
ax.bar(range(7), vals, color=BLUE, width=0.7, linewidth=0, label='All cases'); ax.bar(range(7), alc, color=WARN, width=0.7, linewidth=0, label='Alcohol ≤48 h or affirmed')
for i, v in enumerate(vals): ax.text(i, v + 1.5, str(v), ha='center', fontsize=FS - 1, color=INK2)
ax.set_xticks(range(7)); ax.set_xticklabels([d[:2] for d in days]); ax.set_ylim(0, 108); ax.set_yticks(range(0, 101, 25))
ax.legend(frameon=False, fontsize=FS - 0.5, loc='upper right', bbox_to_anchor=(1.02, 1.03)); style(ax)
ax = dpanel(1, 0, f'Environmental state (all {N} records)'); st = E['states']
lab_map = [('Band B or C; velocity >=0.5 m/s', 'B/C, ≥0.5 m/s', AQUA), ('Band B or C; velocity 0.25-<0.5 m/s', 'B/C, 0.25–0.5 m/s', WARN), ('Band B or C; velocity <0.25 m/s', 'B/C, <0.25 m/s', CRIT), ('Band A or at its limit', 'At/above limit', CRIT), ('Band D (below hot threshold)', 'Band D', BLUE), ('Not assessable', 'Not assessable', MUTED)]
labs = [l for k, l, cc in lab_map]; vv = [st.get(k, 0) for k, l, cc in lab_map]; cols = [cc for k, l, cc in lab_map]; yy = np.arange(len(labs))[::-1]
ax.barh(yy, vv, color=cols, height=0.62, linewidth=0)
for y0, v in zip(yy, vv): ax.text(v + 2.5, y0, f'{v} ({v / N:.0%})', va='center', fontsize=FS - 1, color=INK2)
ax.set_yticks(yy); ax.set_yticklabels(labs); ax.set_xlim(0, 175); ax.set_xticks(range(0, 151, 50)); style(ax, ygrid=False, xgrid=True)
ax = dpanel(1, 1, 'Coded statements by source'); order = ['Ventilation controls absent or substandard', 'Ore or material accumulation obstructing airflow', 'Water, wet conditions or fissure heat', 'Local cooling equipment (cooling car, in-stope cooler)', 'Fan not operating, not installed or obstructed', 'Mine-level refrigeration (fridge plant, bulk air cooler, chilled water)', 'Ventilation column or duct leakage or distance', 'Work organisation (staff shortage, overtime, long shift, extra task)', 'Entry examination, temperature measurement or supervision not done']
short = ['Ventilation controls', 'Ore obstruction', 'Water/wet/fissure', 'Local cooling', 'Fan not operating', 'Mine refrigeration', 'Column/duct leakage', 'Work organisation', 'Entry check/supervision']
yy = np.arange(len(order))[::-1]; iv = [M[k]['I'] for k in order]; cv = [M[k]['C'] for k in order]
ax.barh(yy + 0.19, iv, height=0.36, color=BLUE, label='Investigation', linewidth=0); ax.barh(yy - 0.19, cv, height=0.36, color=ORANGE, label='Complaint', linewidth=0)
for y0, v in zip(yy, iv): ax.text(v + 1.2, y0 + 0.19, str(v), va='center', fontsize=FS - 1.5, color=INK2)
ax.set_yticks(yy); ax.set_yticklabels(short); ax.set_xlim(0, 84); ax.set_xticks(range(0, 81, 20)); ax.legend(frameon=False, fontsize=FS - 1, loc='center right', bbox_to_anchor=(1.02, 0.40)); style(ax, ygrid=False, xgrid=True)
ax = dpanel(2, 0, 'Top raise lines: cases (vent-control statements)'); rl9 = pd.read_csv(RL).head(8); yy = np.arange(len(rl9))[::-1]
ax.barh(yy, rl9.cases, color=[BLUE if s_ == 'A' else ORANGE for s_ in rl9.shaft], height=0.62, linewidth=0)
for y0, (n, vc) in zip(yy, zip(rl9.cases, rl9.vent_controls)): ax.text(n + 0.3, y0, f'{n} ({vc})', va='center', fontsize=FS - 1, color=INK2)
ax.set_yticks(yy); ax.set_yticklabels(rl9.raise_code); ax.set_xlim(0, 16); ax.set_xticks(range(0, 13, 4)); style(ax, ygrid=False, xgrid=True)
ax = dpanel(2, 1, 'Worker-context indicators'); pf = [('Any indicator', P['any']), ('Medical condition', P['med']), ('Previous episode', P['prev']), ('Acute illness', P['acute']), ('Alcohol ≤48 h', P['alc']['Within 48 h or affirmed']), ('Poorly controlled', P['ctrl']['Poorly or partly controlled'])]
yy = np.arange(len(pf))[::-1]; ax.barh(yy, [v for k, v in pf], color=[INK2, BLUE, BLUE, BLUE, WARN, CRIT], height=0.62, linewidth=0)
for y0, (k, v) in zip(yy, pf): ax.text(v + 2.5, y0, f'{v} ({v / N:.0%})', va='center', fontsize=FS - 1, color=INK2)
ax.set_yticks(yy); ax.set_yticklabels([k for k, v in pf]); ax.set_xlim(0, 150); ax.set_xticks(range(0, 151, 50)); ax.set_ylim(-1.5, len(pf) - 0.4)
ax.text(0, -1.05, f"Screening ≤12 months: {S['hts']['le12']}/{S['hts']['valid']}", ha='left', va='center', fontsize=FS - 1, color=INK2); style(ax, ygrid=False, xgrid=True)
fig.text(0.02, 0.012, 'Proportions of recorded cases, not rates. 0.5 m/s is a provisional analytical screen, not a compliance criterion.\nCoded statements are adjudicated documentary mentions (single reviewer), not verified control failures.\nRaise-line codes are assigned in order of case count; the crosswalk is held by the mine.', fontsize=7.8, color=MUTED, linespacing=1.4)
fig.savefig(f'{OUT}/Figure_9_historical_dashboard.png'); plt.close(fig)

# ------------------------------------------------------------------ Figure 10: future-state dashboard demonstrator (deterministic synthetic data), portrait
rng = np.random.default_rng(20260901)
t = pd.date_range('2026-02-18 06:00', '2026-02-18 14:00', freq='5min'); n = len(t); h = np.arange(n) / 12.0
wb = 29.6 + 0.35 * np.sin(h / 2.2) + rng.normal(0, 0.07, n); db = 31.8 + 0.3 * np.sin(h / 2.5 + 1) + rng.normal(0, 0.08, n); vel = 1.05 + 0.05 * np.sin(h / 1.7) + rng.normal(0, 0.02, n)
deg = (h >= 3.5) & (h < 5.4)
ramp = np.clip((h - 3.5) / 1.9, 0, 1) * deg; vel = np.where(deg, 1.0 - 0.55 * ramp, vel); wb = np.where(deg, wb + 1.4 * ramp, wb); db = np.where(deg, db + 1.1 * ramp, db)
after = h >= 5.4; vel = np.where(after, 1.1 + 0.02 * rng.normal(size=n), vel); wb = np.where(after, 29.3 + 0.1 * rng.normal(size=n) - 0.1 * (h - 5.4), wb); db = np.where(after, 31.9 + 0.1 * rng.normal(size=n), db)
pd.DataFrame({'time': t, 'wet_bulb_C': np.round(wb, 2), 'dry_bulb_C': np.round(db, 2), 'air_velocity_m_s': np.round(vel, 3), 'degraded_control_period': deg}).to_csv(f'{OUT}/Figure_10_synthetic_time_series.csv', index=False)
fig = plt.figure(figsize=(7.2, 8.8))
fig.text(0.02, 0.978, 'Future-state current-shift dashboard (thermal and ventilation control)', fontsize=12.5, fontweight='bold', color=NAVY, va='top')
fig.text(0.02, 0.952, 'ILLUSTRATIVE SYNTHETIC DATA — NOT MINE PERFORMANCE\nDemonstrates proposed fields, logic and workflow only', fontsize=8.6, fontweight='bold', color=CRIT, va='top', linespacing=1.35)
axk = fig.add_axes([0.02, 0.835, 0.965, 0.08]); axk.set_xlim(0, 4); axk.set_ylim(0, 1); axk.axis('off')
for i, (lab, val, sub, col) in enumerate([('VALID DATA AVAILABILITY', '96%', 'Points received and valid', AQUA), ('AREAS REQUIRING REVIEW', '2', 'Rule-based triage', ORANGE), ('DEGRADED CRITICAL CONTROLS', '1', 'Raise ventilation, cooling', CRIT), ('AWAITING VERIFICATION', '1', 'Not closed until measured', NAVY)]):
    axk.add_patch(Rectangle((i + 0.02, 0.0), 0.96, 1.0, facecolor='#f6f5f1', edgecolor='none')); axk.add_patch(Rectangle((i + 0.02, 0.92), 0.96, 0.08, facecolor=col, edgecolor='none'))
    axk.text(i + 0.06, 0.70, lab, fontsize=7.2, color=INK2); axk.text(i + 0.06, 0.33, val, fontsize=15, fontweight='bold', color=INK); axk.text(i + 0.06, 0.08, sub, fontsize=7.4, color=MUTED)
ax = fig.add_axes([0.10, 0.535, 0.80, 0.25]); ax2 = ax.twinx()
ax.axvspan(t[deg][0], t[deg][-1], color='#fbe9e9', zorder=0, label='Synthetic degraded-control period')
ax.plot(t, wb, color=BLUE, lw=1.5, label='Wet-bulb (°C)'); ax.plot(t, db, color=ORANGE, lw=1.5, label='Dry-bulb (°C)'); ax2.plot(t, vel, color=AQUA, lw=1.5, label='Air velocity (m/s)')
ax.set_ylabel('Temperature (°C)', fontsize=FS); ax2.set_ylabel('Air velocity (m/s)', color=AQUA, fontsize=FS); ax2.tick_params(axis='y', colors=AQUA); ax2.spines['right'].set_visible(True); ax2.spines['right'].set_color(AQUA)
ax.set_title('Time-aligned environmental trend and control event (synthetic)', fontsize=FS + 1, loc='left', color=INK, fontweight='bold')
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=FS - 0.5, loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M')); style(ax); ax.tick_params(labelsize=FS); ax2.tick_params(labelsize=FS)
def panel(x0, y0, w, hgt, title):
    axp = fig.add_axes([x0, y0, w, hgt]); axp.axis('off'); axp.set_xlim(0, 1); axp.set_ylim(0, 1)
    axp.text(0, 1.0, title, fontsize=FS + 1, fontweight='bold', color=INK, va='top'); return axp
axw = panel(0.04, 0.245, 0.44, 0.19, 'Active event workflow')
for k, (tm, ttl, sub, st, col) in enumerate([('09:35', 'Trend rule', 'Air-velocity decline and wet-bulb rise', 'Detected', ORANGE), ('09:40', 'Acknowledged', 'Ventilation officer', 'On time', AQUA), ('09:48', 'Manual verification', 'Paired portable reading', 'Valid', AQUA), ('10:02', 'Control action', 'Duct and brattice restored', 'Actioned', AQUA), ('10:25', 'Post-control check', 'Trend recovering', 'Verify', ORANGE)]):
    y0 = 0.80 - k * 0.168; axw.text(0.0, y0, tm, fontsize=FS - 0.5, fontweight='bold', color=NAVY, va='top'); axw.text(0.17, y0, ttl, fontsize=FS - 0.5, fontweight='bold', color=INK, va='top'); axw.text(0.17, y0 - 0.075, sub, fontsize=FS - 1, color=INK2, va='top'); axw.text(1.0, y0, st, fontsize=FS - 0.5, color=col, ha='right', va='top')
    axw.plot([0, 1], [y0 - 0.135, y0 - 0.135], color=GRID, lw=0.6)
axs = panel(0.54, 0.245, 0.44, 0.19, 'Control and data-assurance state')
for k, (lab, val) in enumerate([('Sensor health', 'Online'), ('Calibration', 'Valid until 2026-03-31'), ('Paired manual check', 'Completed 09:48'), ('Measurement status', 'Valid after review'), ('Control telemetry', 'Restored'), ('Action close-out', 'Awaiting sign-off')]):
    axs.text(0.0, 0.80 - k * 0.15, lab, fontsize=FS - 0.5, color=INK2, va='top'); axs.text(0.50, 0.80 - k * 0.15, val, fontsize=FS - 0.5, fontweight='bold', color=INK, va='top')
axg = panel(0.04, 0.055, 0.94, 0.16, 'Proposed decision guardrails')
guards = ['Use mine-approved code-of-practice rules, not generic thresholds', 'Flag suspect data separately from a safe condition', 'Require manual, competent verification for defined events', 'Record action owner, due time and post-control measurement', 'Retain auditable source data and sign-off history']
for k, g in enumerate(guards):
    axg.text(0.0, 0.76 - k * 0.165, '• ' + g, fontsize=FS - 0.5, color=INK2, va='top')
fig.text(0.02, 0.012, 'Synthetic values generated by the analysis scripts (seed 20260901) solely to illustrate future-state\nfunctionality; no field performance, compliance or effectiveness claim is made.', fontsize=7.8, fontweight='bold', color=CRIT, linespacing=1.4)
fig.savefig(f'{OUT}/Figure_10_future_state_dashboard_SYNTHETIC.png'); plt.close(fig)
print('figures written')
