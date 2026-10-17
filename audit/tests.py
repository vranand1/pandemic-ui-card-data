"""Staff econometrician audit.

A. Monte Carlo on simulated staggered panels with unit and week effects, AR(1) noise, heterogeneous
   dynamic effects, and a spurious pre-trend option. Checks: bias of att_gt/aggregate and pair_event;
   size of the randomization test under the sharp null; coverage of the 95% randomization interval.
B. Independent re-implementation of the headline estimates with OLS (unit and week fixed effects, cohort by
   cohort against never-treated states) and comparison to the hand-coded estimator to 1e-8.
C. Replication of the smoothing-window effect: old 13-day average vs Saturday value, same code otherwise.
D. Treatment-date and pair-construction checks.
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
from common import *
from state_panel import load_state
from state_analysis import wide, design
import statsmodels.formula.api as smf
import border as Bd

rng = np.random.default_rng(2026)
REPORT = []
def log(s):
    print(s); REPORT.append(s)


# ---------------- A. Monte Carlo ----------------
def sim_panel(n_units=49, n_weeks=27, cohorts=(16, 17, 18, 19, 20), n_treated=(4, 7, 10, 1, 1), tau=None, rho=0.5,
              pretrend=0.0, het=True, seed=0):
    r = np.random.default_rng(seed)
    weeks = pd.date_range("2021-03-06", periods=n_weeks, freq="7D")
    units = [f"U{i:02d}" for i in range(n_units)]
    alpha = r.normal(0, 2, n_units); gamma = np.cumsum(r.normal(0, 0.5, n_weeks))
    eps = np.zeros((n_units, n_weeks)); e0 = r.normal(0, 1, n_units)
    for t in range(n_weeks):
        e0 = rho * e0 + r.normal(0, 1, n_units); eps[:, t] = e0
    Y = alpha[:, None] + gamma[None, :] + eps
    perm = list(r.permutation(units)); coh = {}; i = 0
    for c, n in zip(cohorts, n_treated):
        coh[weeks[c]] = perm[i:i + n]; i += n
    ctl = perm[i:]
    truth = {}
    for g, m in coh.items():
        gi = list(weeks).index(g)
        for u in m:
            ui = units.index(u)
            if pretrend:
                Y[ui, :] += pretrend * (np.arange(n_weeks) - gi)
            for t in range(n_weeks):
                e = t - gi
                if e >= 0 and tau is not None:
                    eff = tau * (1 + 0.1 * e) * (1.5 if (het and gi == cohorts[0]) else 1.0)
                    Y[ui, t] += eff; truth.setdefault((g, e), []).append(eff)
    W = pd.DataFrame(Y, index=units, columns=weeks)
    return W, coh, ctl, truth


def true_post_att(truth, coh):
    rows = [(g, e, np.mean(v), len(coh[g])) for (g, e), v in truth.items() if 0 <= e <= 8]
    r = pd.DataFrame(rows, columns=["g", "e", "att", "n"])
    return np.average(r.att, weights=r.n)


def mc_state(R=120, tau=-1.0, base="premean", pretrend=0.0):
    errs, covers, pvals = [], [], []
    for s in range(R):
        W, coh, ctl, truth = sim_panel(tau=tau, seed=s, pretrend=pretrend)
        est = aggregate(att_gt(W, coh, ctl, base=base))[1]
        tr = true_post_att(truth, coh) if tau else 0.0
        errs.append(est - tr)
        if s < 30:   # RI is the slow part
            sizes = {g: len(m) for g, m in coh.items()}
            null = randomization_inference(lambda c, k: aggregate(att_gt(W, c, k, base=base))[1], list(W.index), sizes, B=150, seed=s)
            if tau == 0:
                pvals.append((np.abs(null) >= abs(est)).mean())
            else:
                covers.append(abs(est - tr) <= np.quantile(np.abs(null), .95))
    return np.mean(errs), np.std(errs), (np.mean(np.array(pvals) <= .05) if pvals else None), (np.mean(covers) if covers else None)


def mc_border(R=60, tau=-1.0):
    errs = []
    for s in range(R):
        r = np.random.default_rng(1000 + s)
        weeks = pd.date_range("2021-03-06", periods=27, freq="7D"); n_pairs = 140
        g_opts = [weeks[16], weeks[17], weeks[18]]
        rows, Y = [], {}
        for p in range(n_pairs):
            g = g_opts[p % 3]; gi = list(weeks).index(g)
            common = np.cumsum(r.normal(0, 1, 27))                       # shared local shock
            for side in ("t", "c"):
                e0 = 0; ser = []
                for t in range(27):
                    e0 = 0.4 * e0 + r.normal(0, 1.5); ser.append(e0)
                y = common + np.array(ser) + r.normal(0, 3)
                if side == "t":
                    y = y + np.array([tau if t - gi >= 0 else 0 for t in range(27)])
                Y[f"{side}{p}"] = y
            rows.append(dict(pair=p, t_fips=f"t{p}", c_fips=f"c{p}", g=g, segment=f"s{p % 10}", t_state="X", c_state="Y"))
        W = pd.DataFrame(Y).T; W.columns = weeks; pr = pd.DataFrame(rows)
        est = Bd.pair_event(W, pr, base="premean")[1]
        errs.append(est - tau)
    return np.mean(errs), np.std(errs)


# ---------------- B. OLS re-implementation ----------------
def ols_cohort_att(df, st, y="y_spend_all", pre=(-8, -2), post=(0, 8)):
    """For each cohort g: OLS of y on unit FE + week FE + D (treated x post) using cohort g and never-treated
    states, restricted to event weeks in pre window and post window. Then n-weighted average of cohort ATTs
    with the same (g, e) cell weighting as `aggregate`."""
    cohorts, controls = design(st)
    rows = []
    for g, m in cohorts.items():
        d = df[df.stateabbrev.isin(m + controls)].copy()
        d["e"] = ((d.week - g) / WEEK).round().astype(int)
        d = d[((d.e >= pre[0]) & (d.e <= pre[1])) | ((d.e >= post[0]) & (d.e <= post[1]))]
        d["D"] = (d.stateabbrev.isin(m) & (d.e >= 0)).astype(int)
        d = d.dropna(subset=[y])
        fit = smf.ols(f"{y} ~ D + C(stateabbrev) + C(week)", data=d).fit()
        n_post = d[d.stateabbrev.isin(m) & (d.e >= 0)].e.nunique()
        rows.append(dict(g=g, n=len(m), att=fit.params["D"], n_post_weeks=n_post))
    r = pd.DataFrame(rows)
    # aggregate() weights each (g, e) cell by n; equivalently weight cohort ATT by n x number of post weeks
    return np.average(r.att, weights=r.n * r.n_post_weeks), r


def ols_border(W, pr, pre=(-8, -2), post=(0, 8)):
    """Stacked OLS with pair-by-week and pair-by-side fixed effects; D = treated side x post."""
    recs = []
    for row in pr.itertuples():
        for side, f in (("t", row.t_fips), ("c", row.c_fips)):
            for t in W.columns:
                e = int((t - row.g) / WEEK)
                if (pre[0] <= e <= pre[1]) or (post[0] <= e <= post[1]):
                    recs.append(dict(pair=row.pair, side=side, week=t, y=W.loc[f, t], D=int(side == "t" and e >= 0)))
    d = pd.DataFrame(recs)
    d["pw"] = d.pair + "_" + d.week.astype(str); d["ps"] = d.pair + "_" + d.side
    # demean within pair-week and pair-side (two-way within transformation by alternating projections)
    y, D = d.y.values.astype(float), d.D.values.astype(float)
    for _ in range(50):
        for key in ("pw", "ps"):
            gm = pd.Series(y).groupby(d[key].values).transform("mean").values; y = y - gm
            gm = pd.Series(D).groupby(d[key].values).transform("mean").values; D = D - gm
    return float((D * y).sum() / (D * D).sum())


# ---------------- C. smoothing window ----------------
def smoothing_check():
    a = pd.read_csv(RAW / "Affinity_-_State_-_Daily.csv", na_values=".")
    new = weekly_from_daily(a, "statefips", ["spend_all"])                          # new: Saturday value
    a["date"] = pd.to_datetime(dict(year=a.year, month=a.month, day=a.day)); a["wk"] = a.date.map(week_end)
    old = a.groupby(["statefips", "wk"]).spend_all.mean().reset_index().rename(columns={"wk": "week"})   # old: mean of 7-day MA within week
    st = state_table(); st = st[st.stateabbrev != "DC"]
    out = {}
    for name, sp in (("13-day window (old)", old), ("Saturday value (new)", new)):
        d = sp.merge(st[["statefips", "stateabbrev"]], on="statefips"); d = d[(d.week >= START) & (d.week <= STOP)]
        d["y"] = logpts(d.spend_all); W = d.pivot(index="stateabbrev", columns="week", values="y")
        cohorts, controls = design(st)
        out[name] = {b: aggregate(att_gt(W, cohorts, controls, base=b))[1] for b in ("g-1", "premean")}
    return out


if __name__ == "__main__":
    log("A. Monte Carlo (state estimator, 49 units, cohorts of 4/7/10/1/1, AR(1) noise, heterogeneous dynamic effects)")
    for base in ("g-1", "premean"):
        b, s, _, cov = mc_state(R=120, tau=-1.0, base=base)
        log(f"   base={base:8s} true effect -1 (avg -1.3 with dynamics): bias={b:+.3f} sd={s:.3f} RI-95% coverage={cov:.2f}")
    b, s, size, _ = mc_state(R=120, tau=0.0, base="premean")
    log(f"   sharp null, premean: bias={b:+.3f} sd={s:.3f} RI rejection rate at 5% = {size:.3f}")
    b, s, _, _ = mc_state(R=80, tau=0.0, base="premean", pretrend=0.1)
    log(f"   spurious pre-trend 0.1/week, no effect: estimator bias={b:+.3f} (expected: biased; the pre-trend diagnostics must catch this)")
    b, s = mc_border(R=60, tau=-1.0)
    log(f"   border pair estimator, shared local shocks, true effect -1: bias={b:+.3f} sd={s:.3f}")

    log("B. Independent OLS re-implementation (unit and week FE, cohort by cohort vs never-treated)")
    df, st = load_state(); st = st[st.stateabbrev != "DC"]; df = df[df.stateabbrev != "DC"]
    cohorts, controls = design(st)
    for y in ("y_spend_all", "y_claims"):
        hand = aggregate(att_gt(wide(df, y), cohorts, controls, base="premean"))[1]
        ols, r = ols_cohort_att(df, st, y=y)
        log(f"   {y:12s} hand-coded premean = {hand:+.6f} | OLS = {ols:+.6f} | diff = {hand - ols:+.2e}")
    W, geo, expo = Bd.load_counties(); adj = Bd.adjacency(); pr = Bd.build_pairs(st, W, geo, adj)
    hand = Bd.pair_event(W, pr, base="premean")[1]
    ols = ols_border(W, pr)
    log(f"   border premean hand-coded = {hand:+.4f} | stacked OLS with pair x week and pair x side FE = {ols:+.4f} (differ by cell weighting across cohorts with truncated post windows)")

    log("C. Smoothing window check (same estimator, two weekly aggregations)")
    for k, v in smoothing_check().items():
        log(f"   {k:22s} g-1 base = {v['g-1']:+.3f} | premean base = {v['premean']:+.3f}")

    log("D. Design checks")
    log(f"   cohorts: " + "; ".join(f"{g.date()}: {' '.join(m)}" for g, m in cohorts.items()))
    log(f"   never-treated ({len(controls)}): {' '.join(controls)}")
    seg = pr.groupby('segment').size().sort_values(ascending=False)
    log(f"   border pairs {len(pr)}, segments {len(seg)}, largest: {seg.head(6).to_dict()}; treated counties used in >1 pair: {(pr.t_fips.value_counts() > 1).sum()}")
    u = pd.read_csv(RAW / "UI_Claims_-_State_-_Weekly.csv", na_values=".")
    u["week"] = pd.to_datetime(dict(year=u.year, month=u.month, day=u.day_endofweek))
    ia = u[(u.statefips == 19) & (u.week.between("2021-06-05", "2021-06-26"))][["week", "contclaims_count_combined", "contclaims_count_peuc", "contclaims_count_pua"]]
    log("   Iowa claims around June 12 end date (claims dated by the week they cover):\n" + ia.to_string(index=False))
    (ROOT / "audit" / "audit_report.txt").write_text("\n".join(REPORT))
