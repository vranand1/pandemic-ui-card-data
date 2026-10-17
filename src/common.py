"""Shared definitions: treatment dates, sample window, outcome construction, estimators, inference.

Treatment: the week (ending Saturday) that contains the first day without federal pandemic UI.
Sources: Opportunity Insights Policy Milestones file, cross-checked against NELP's Aug 24, 2021 tracker.
South Carolina (June 30) is missing from the OI file and comes from NELP.
"""
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT, FIG = ROOT / "data" / "raw", ROOT / "out", ROOT / "fig"
OUT.mkdir(exist_ok=True); FIG.mkdir(exist_ok=True)
WEEK = pd.Timedelta(days=7)

# Date federal programs ended in the state, and whether it ended all programs or only the $300 FPUC supplement.
END = {
    "AK": ("2021-06-12", "fpuc_only"), "IA": ("2021-06-12", "all"), "MS": ("2021-06-12", "all"), "MO": ("2021-06-12", "all"),
    "AL": ("2021-06-19", "all"), "ID": ("2021-06-19", "all"), "NE": ("2021-06-19", "all"), "NH": ("2021-06-19", "all"),
    "ND": ("2021-06-19", "all"), "WV": ("2021-06-19", "all"), "WY": ("2021-06-19", "all"),
    "AR": ("2021-06-26", "all"), "FL": ("2021-06-26", "fpuc_only"), "GA": ("2021-06-26", "all"), "OH": ("2021-06-26", "fpuc_only"),
    "OK": ("2021-06-26", "all"), "SD": ("2021-06-26", "all"), "TX": ("2021-06-26", "all"), "UT": ("2021-06-26", "all"),
    "MT": ("2021-06-27", "all"), "SC": ("2021-06-30", "all"), "TN": ("2021-07-03", "all"), "AZ": ("2021-07-10", "fpuc_only"),
    "LA": ("2021-07-31", "fpuc_only"),
}
DROP = {"IN", "MD"}            # ended benefits, then courts ordered them restored
START, STOP = "2021-03-06", "2021-09-04"
ANNOUNCE_BASE = pd.Timestamp("2021-05-01")   # last week before any state announced (Montana, May 4)


def week_end(d):
    d = pd.Timestamp(d)
    return d + pd.Timedelta(days=(5 - d.weekday()) % 7)


def first_treated_week(end_date):
    return week_end(pd.Timestamp(end_date) + pd.Timedelta(days=1))


def state_table():
    geo = pd.read_csv(RAW / "GeoIDs_-_State.csv")
    geo = geo[~geo.stateabbrev.isin(DROP)].copy()
    geo["g"] = geo.stateabbrev.map(lambda s: first_treated_week(END[s][0]) if s in END else pd.NaT)
    geo["kind"] = geo.stateabbrev.map(lambda s: END[s][1] if s in END else "never")
    geo["treated"] = geo.g.notna()
    return geo


def weekly_from_daily(a, idcol, cols):
    """Take the Saturday observation of the 7-day moving average: the plain average of that Sunday-to-Saturday week."""
    a = a.copy()
    a["date"] = pd.to_datetime(dict(year=a.year, month=a.month, day=a.day))
    a = a[a.date.dt.weekday == 5]
    a = a.rename(columns={"date": "week"})
    return a[[idcol, "week"] + cols]


def logpts(x):
    return 100 * np.log1p(x)


def rel_event(W, g):
    """Event time for each column (week) given cohort date g."""
    return ((W.columns - g) / WEEK).astype(int)


# ---------- Staggered DiD, never-treated controls (Callaway and Sant'Anna 2021 style) ----------

def att_gt(W, cohorts, controls, base="g-1", weights=None, emin=-12, emax=8):
    """W: unit x week outcome matrix. cohorts: {g: [units]}. controls: [units].
    base: 'g-1' (universal base, week before treatment) or a Timestamp (fixed pre-announcement base).
    Returns long frame of ATT(g, e) with cohort sizes, and a dict of overall and pre averages."""
    rows = []
    for g, members in cohorts.items():
        m = [u for u in members if u in W.index]
        bT, bC = base_values(W, g, base, m, controls)
        if bT is None:
            continue
        dT = W.loc[m].sub(bT, axis=0)
        dC = W.loc[controls].sub(bC, axis=0)
        if weights is None:
            mT, mC = dT.mean(), dC.mean()
        else:
            mT = _wmean(dT, weights.reindex(m)); mC = _wmean(dC, weights.reindex(controls))
        att = mT - mC
        for t, e in zip(W.columns, rel_event(W, g)):
            if emin <= e <= emax and not np.isnan(att[t]):
                rows.append((g, e, att[t], len(m)))
    r = pd.DataFrame(rows, columns=["g", "e", "att", "n"])
    return r


def base_values(W, g, base, m, controls, pre_lo=-8, pre_hi=-2):
    """Per-unit baseline level. 'g-1': week before treatment. 'premean': mean of event weeks pre_lo..pre_hi.
    Otherwise a fixed calendar week (Timestamp)."""
    e = rel_event(W, g)
    if base == "g-1":
        b = g - WEEK
        if b not in W.columns:
            return None, None
        return W.loc[m, b], W.loc[controls, b]
    if base == "premean":
        cols = [t for t, ee in zip(W.columns, e) if pre_lo <= ee <= pre_hi]
        return W.loc[m, cols].mean(axis=1), W.loc[controls, cols].mean(axis=1)
    b = pd.Timestamp(base)
    return W.loc[m, b], W.loc[controls, b]


def _wmean(d, w):
    """Weighted column means, normalizing weights only over non-missing entries (fixes the DC bug)."""
    w = w.astype(float)
    num = d.mul(w, axis=0).sum(min_count=1)
    den = d.notna().mul(w, axis=0).sum()
    return num / den


def aggregate(r, emin_pre=-12):
    ev = r.groupby("e").apply(lambda x: np.average(x.att, weights=x.n), include_groups=False)
    post = r[r.e >= 0]; pre = r[(r.e <= -2) & (r.e >= emin_pre)]
    return ev, (np.average(post.att, weights=post.n) if len(post) else np.nan), (np.average(pre.att, weights=pre.n) if len(pre) else np.nan)


def pretrend_slope(ev, emin=-8, emax=-1):
    """OLS slope of pre-period event-time estimates (log points per week)."""
    x = np.array([e for e in ev.index if emin <= e <= emax]); y = ev.reindex(x).values
    x = x - x.mean()
    return float((x * (y - y.mean())).sum() / (x ** 2).sum())


def linear_trend_adjusted_post(ev, slope):
    """Post average after extrapolating the pre-period linear trend (Dobkin et al. 2018 style, one of several bounds)."""
    post = [e for e in ev.index if e >= 0]
    return float(np.mean([ev[e] - slope * (e + 1) for e in post]))


def kernel_weights(exposure, target_mean, bw=1.5):
    """Gaussian kernel weights on exposure distance to the treated mean, normalized to sum to the number of units."""
    w = np.exp(-0.5 * ((exposure - target_mean) / bw) ** 2)
    return w / w.mean()


def randomization_inference(stat_fn, units, n_treated_by_cohort, B=1000, seed=11):
    """Reassign cohorts at random across units (keeping cohort sizes), recompute the statistic.
    Returns the null distribution. Valid for the sharp null of no effect for anyone."""
    rng = np.random.default_rng(seed)
    units = list(units); draws = []
    for _ in range(B):
        perm = list(rng.permutation(units)); cohorts = {}; i = 0
        for g, n in n_treated_by_cohort.items():
            cohorts[g] = perm[i:i + n]; i += n
        draws.append(stat_fn(cohorts, perm[i:]))
    return np.array(draws)
