"""Border-county design: adjacent county pairs across a state line where one state ended federal
pandemic UI early and the other kept it to September 6, 2021.

Estimator: for each pair, difference in card spending (treated county minus control county), measured
relative to a base week, averaged across pairs by event time. Equivalent to a DiD with pair-by-week fixed
effects. Inference: (1) randomization inference that reassigns treatment across STATES (keeping cohort
sizes) and rebuilds the pairs, so the test respects state-level assignment; (2) cluster bootstrap by border
segment (treated state x control state) as a check.
Exposure heterogeneity: counties split by the regular initial UI claims rate in Mar to May 2021 (OI, 30 states).
"""
import numpy as np, pandas as pd
from common import *

EMIN, EMAX = -10, 8


def load_counties():
    geo = pd.read_csv(RAW / "GeoIDs_-_County.csv")
    a = pd.read_csv(RAW / "Affinity_-_County_-_Daily.csv", na_values=".")
    a = a[a.freq == "d"]
    sp = weekly_from_daily(a, "countyfips", ["spend_all"])
    sp = sp[(sp.week >= START) & (sp.week <= STOP)]
    sp["y"] = logpts(sp.spend_all)
    W = sp.pivot(index="countyfips", columns="week", values="y")
    # keep counties with a complete series
    W = W.dropna()
    u = pd.read_csv(RAW / "UI_Claims_-_County_-_Weekly.csv", na_values=".")
    u["week"] = pd.to_datetime(dict(year=u.year, month=u.month, day=u.day_endofweek))
    expo = u[(u.week >= "2021-03-01") & (u.week <= "2021-05-29")].groupby("countyfips").initclaims_rate_regular.mean()
    geo = geo.set_index("countyfips")
    return W, geo, expo


def adjacency():
    rows, cur = [], None
    for line in open(RAW / "county_adjacency.txt", encoding="latin-1"):
        p = line.rstrip("\n").split("\t")
        if p[0]:
            cur = int(p[1])
        if len(p) >= 4 and p[3]:
            rows.append((cur, int(p[3])))
    adj = pd.DataFrame(rows, columns=["a", "b"])
    adj = adj[adj.a != adj.b]
    adj["sa"], adj["sb"] = adj.a // 1000, adj.b // 1000
    return adj[adj.sa != adj.sb]


def build_pairs(st, W, geo, adj):
    """Pairs (treated county, control county) with both counties in the card data."""
    fips2abbr = st.set_index("statefips").stateabbrev
    gmap = st.set_index("stateabbrev").g
    adj = adj[adj.sa.isin(fips2abbr.index) & adj.sb.isin(fips2abbr.index)].copy()
    adj["A"], adj["Bb"] = adj.sa.map(fips2abbr), adj.sb.map(fips2abbr)
    tr = adj.A.map(gmap).notna(); ct = adj.Bb.map(gmap).isna()
    pr = adj[tr & ct & adj.a.isin(W.index) & adj.b.isin(W.index)].copy()
    pr = pr.rename(columns={"a": "t_fips", "b": "c_fips", "A": "t_state", "Bb": "c_state"})
    pr["g"] = pr.t_state.map(gmap)
    pr["segment"] = pr.t_state + "-" + pr.c_state
    pr["pair"] = pr.t_fips.astype(str) + "_" + pr.c_fips.astype(str)
    return pr[["pair", "t_fips", "c_fips", "t_state", "c_state", "segment", "g"]].reset_index(drop=True)


def pair_weights(pr, pop):
    """Harmonic mean of the two counties' populations, divided by the number of pairs each county appears in,
    so a large county paired with three neighbors does not enter three times at full weight."""
    pt, pc = pr.t_fips.map(pop).astype(float), pr.c_fips.map(pop).astype(float)
    hm = 2 * pt * pc / (pt + pc)
    reuse = pr.t_fips.map(pr.t_fips.value_counts()) * pr.c_fips.map(pr.c_fips.value_counts())
    return (hm / np.sqrt(reuse)).values


def pair_event(W, pr, base="g-1", weights=None):
    """Average over pairs of [ (yT_t - yT_b) - (yC_t - yC_b) ] by event time; plus overall post and pre.
    weights: None (equal) or 'pop' (pair_weights with county_pop2019 from the global POP series)."""
    rows = []
    for g, grp in pr.groupby("g"):
        bT, bC = base_values(W, g, base, list(grp.t_fips), list(grp.c_fips))
        dT = W.loc[grp.t_fips].sub(bT.values, axis=0).values
        dC = W.loc[grp.c_fips].sub(bC.values, axis=0).values
        d = dT - dC
        w = np.ones(len(grp)) if weights is None else pair_weights(grp, weights)
        for j, (t, e) in enumerate(zip(W.columns, rel_event(W, g))):
            if EMIN <= e <= EMAX:
                rows.append((g, e, np.average(d[:, j], weights=w), len(grp), w.sum()))
    r = pd.DataFrame(rows, columns=["g", "e", "att", "n", "wsum"])
    ev = r.groupby("e").apply(lambda x: np.average(x.att, weights=x.wsum), include_groups=False)
    post = r[r.e >= 0]; pre = r[(r.e <= -2)]
    return ev, np.average(post.att, weights=post.wsum), np.average(pre.att, weights=pre.wsum)


def ri_states(st, W, geo, adj, pr_stat_fn, B=1000, seed=5, subset_fn=None):
    """Randomization inference over state assignment: permute the (cohort, kind) labels across states, rebuild
    the pairs, apply the same subset rule the real specification used, recompute the statistic."""
    rng = np.random.default_rng(seed)
    states = st.copy()
    labels = list(zip(states.g, states.kind))            # (NaT, 'never') for controls
    base_states = list(states.stateabbrev)
    draws = []
    for _ in range(B):
        perm = rng.permutation(len(labels))
        fake = states.copy()
        fake["g"] = [labels[j][0] for j in perm]; fake["kind"] = [labels[j][1] for j in perm]
        fake["treated"] = fake.g.notna()
        pr = build_pairs(fake, W, geo, adj)
        if subset_fn is not None and len(pr):
            pr = subset_fn(pr, fake)
        draws.append(pr_stat_fn(pr) if len(pr) else np.nan)
    return np.array(draws)


def segment_bootstrap(W, pr, stat_fn, B=999, seed=3):
    rng = np.random.default_rng(seed)
    segs = pr.segment.unique(); out = []
    for _ in range(B):
        pick = rng.choice(segs, size=len(segs), replace=True)
        boot = pd.concat([pr[pr.segment == s] for s in pick], ignore_index=True)
        out.append(stat_fn(boot))
    return np.array(out)


def run(B_ri=1000, B_boot=999):
    st = state_table(); st = st[st.stateabbrev != "DC"]
    W, geo, expo = load_counties()
    adj = adjacency()
    pr = build_pairs(st, W, geo, adj)
    pop = geo.county_pop2019.astype(float)
    print(f"pairs {len(pr)} | treated counties {pr.t_fips.nunique()} | control counties {pr.c_fips.nunique()} | segments {pr.segment.nunique()}")
    print(pr.groupby("segment").size().sort_values(ascending=False).head(12).to_dict())

    results, paths = [], []

    def add(name, subset_fn=None, base="g-1", weights=None, ri=True):
        prs = subset_fn(pr, st) if subset_fn else pr
        ev, post, pre = pair_event(W, prs, base=base, weights=weights)
        slope = pretrend_slope(ev, emin=-8, emax=-1)
        fn = lambda p: pair_event(W, p, base=base, weights=weights)[1]
        bs = segment_bootstrap(W, prs, fn, B=B_boot)
        if ri:
            null = ri_states(st, W, geo, adj, fn, B=B_ri, subset_fn=subset_fn)
            p_ri = float(np.nanmean(np.abs(null) >= abs(post))); sd_ri = float(np.nanstd(null))
            q_lo, q_hi = float(np.nanquantile(null, .025)), float(np.nanquantile(null, .975))
        else:
            p_ri, sd_ri, q_lo, q_hi = np.nan, np.nan, np.nan, np.nan
        results.append(dict(spec=name, base=str(base)[:10], weighted=weights is not None, n_pairs=len(prs),
                            n_segments=prs.segment.nunique(), post_att=post, boot_se=bs.std(ddof=1),
                            boot_lo=np.quantile(bs, .025), boot_hi=np.quantile(bs, .975), ri_sd=sd_ri, ri_p=p_ri,
                            ci_lo=post - q_hi, ci_hi=post - q_lo, pre_avg=pre, pre_minus1=float(ev.get(-1, np.nan)),
                            pre_min=float(ev[ev.index < -1].min()), pre_max=float(ev[ev.index < -1].max()),
                            pre_slope=slope, trend_adj_post=linear_trend_adjusted_post(ev, slope)))
        for e, v in ev.items():
            paths.append(dict(spec=name, e=e, att=v))
        print(f"{name:40s} post={post:6.2f} boot_se={bs.std(ddof=1):5.2f} ri_sd={sd_ri:5.2f} ri_p={p_ri:4.2f} pre={pre:6.2f} slope={slope:6.3f}")

    all_programs = lambda p, s: p[p.t_state.map(s.set_index("stateabbrev").kind) == "all"]
    june = lambda p, s: p[p.g <= "2021-07-03"]
    drop_big = lambda p, s: p[p.segment != p.segment.value_counts().index[0]]          # drop the largest segment, whichever it is
    no_elpaso = lambda p, s: p[~p.t_fips.isin([48141])] if 48141 in set(p.t_fips) else p
    big_pop = lambda p, s: p[(p.t_fips.map(pop) < 500000) & (p.c_fips.map(pop) < 500000)]
    add("border, pre-period mean base", base="premean")
    add("border, g-1 base")
    add("border, May 1 base", base=ANNOUNCE_BASE)
    add("border, population-weighted, premean", base="premean", weights=pop)
    add("border, population-weighted, no El Paso", no_elpaso, base="premean", weights=pop)
    add("border, population-weighted, both counties under 500k", big_pop, base="premean", weights=pop)
    add("border, all-programs states only", all_programs, base="premean")
    add("border, June cohorts only", june, base="premean")
    add("border, drop largest segment", drop_big, base="premean")
    # exposure split on the treated county (where OI county claims exist)
    e_t = pr.t_fips.map(expo)
    have = pr[e_t.notna()].copy(); have["expo"] = e_t[e_t.notna()].values
    med = have.expo.median()
    add("border, high-exposure treated counties", lambda p, s: have[have.expo > med], base="premean", ri=False)
    add("border, low-exposure treated counties", lambda p, s: have[have.expo <= med], base="premean", ri=False)
    # extras: leave-one-segment-out range, per-pair DD distribution, the e = -1 decomposition
    loo = [pair_event(W, pr[pr.segment != s], base="premean")[1] for s in pr.segment.unique()]
    loo_w = [pair_event(W, pr[pr.segment != s], base="premean", weights=pop)[1] for s in pr.segment.unique()]
    dd = []
    for row in pr.itertuples():
        e = rel_event(W, row.g); pre = [t for t, ee in zip(W.columns, e) if -8 <= ee <= -2]; post = [t for t, ee in zip(W.columns, e) if 0 <= ee <= 8]
        d = W.loc[row.t_fips] - W.loc[row.c_fips]; dd.append(d[post].mean() - d[pre].mean())
    pr["dd"] = dd
    # e = -1 week: deviation of each side from its own pre-mean
    devT, devC = [], []
    for row in pr.itertuples():
        e = rel_event(W, row.g); pre = [t for t, ee in zip(W.columns, e) if -8 <= ee <= -2]; m1 = [t for t, ee in zip(W.columns, e) if ee == -1][0]
        devT.append(W.loc[row.t_fips, m1] - W.loc[row.t_fips, pre].mean()); devC.append(W.loc[row.c_fips, m1] - W.loc[row.c_fips, pre].mean())
    extras = dict(loo_min=min(loo), loo_max=max(loo), loo_w_min=min(loo_w), loo_w_max=max(loo_w), exposure_median=med,
                  n_pairs_with_exposure=len(have), dd_median=float(np.median(dd)), dd_share_negative=float(np.mean(np.array(dd) < 0)),
                  dd_sd=float(np.std(dd, ddof=1)), e_minus1_treated_dev=float(np.mean(devT)), e_minus1_control_dev=float(np.mean(devC)))
    res = pd.DataFrame(results)
    res.to_csv(OUT / "border_specs.csv", index=False)
    pd.DataFrame(paths).to_csv(OUT / "border_event.csv", index=False)
    pr.to_csv(OUT / "border_pairs.csv", index=False)
    pd.DataFrame([extras]).to_csv(OUT / "border_extras.csv", index=False)
    print({k: round(v, 3) for k, v in extras.items()})
    return res


if __name__ == "__main__":
    run()
