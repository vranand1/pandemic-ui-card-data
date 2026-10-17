"""State-level staggered DiD with the robustness set a referee would ask for.
Outputs: out/state_specs.csv (one row per specification), out/state_event.csv (event-time paths)."""
import numpy as np, pandas as pd
from common import *
from state_panel import load_state

B_RI = 1000


def wide(df, y):
    return df.pivot(index="stateabbrev", columns="week", values=y)


def design(st, subset="all_treated"):
    tr = st[st.treated]
    if subset == "all_programs":
        tr = tr[tr.kind == "all"]
    elif subset == "fpuc_only":
        tr = tr[tr.kind == "fpuc_only"]
    elif subset == "june":
        tr = tr[tr.g <= "2021-07-03"]
    cohorts = {g: sorted(x.stateabbrev) for g, x in tr.groupby("g")}
    controls = sorted(st[~st.treated].stateabbrev)
    return cohorts, controls


def one_spec(W, cohorts, controls, base="g-1", weights=None):
    r = att_gt(W, cohorts, controls, base=base, weights=weights)
    ev, post, pre = aggregate(r)
    return ev, post, pre


def ri_pvalue(W, cohorts, controls, post, base="g-1", weights=None, B=B_RI, seed=11, weights_fn=None):
    """Placebo distribution: reassign cohorts across the states in the design, recompute the statistic.
    Returns p-value, sd, and the 2.5 / 97.5 percentiles of the null (for a test-inversion interval: est - q97.5, est - q2.5)."""
    units = [u for u in list(W.index) if u in controls or any(u in m for m in cohorts.values())]
    sizes = {g: len(m) for g, m in cohorts.items()}
    def stat(coh, ctl):
        w = weights_fn(coh) if weights_fn is not None else weights     # weights that depend on assignment are rebuilt per draw
        return one_spec(W, coh, ctl, base=base, weights=w)[1]
    null = randomization_inference(stat, units, sizes, B=B, seed=seed)
    p = float((np.abs(null) >= abs(post)).mean())
    return p, float(np.nanstd(null)), float(np.nanquantile(null, .025)), float(np.nanquantile(null, .975))


def run():
    df, st = load_state()
    st = st[st.stateabbrev != "DC"]          # no card data; keep the sample honest
    df = df[df.stateabbrev != "DC"]
    pop = st.set_index("stateabbrev").state_pop2019.astype(float)
    specs, paths = [], []

    expo = df.drop_duplicates("stateabbrev").set_index("stateabbrev").exposure

    def add(name, y, subset="all_treated", base="g-1", weights=None, ri=True, covid_adj=False, control_set="all", drop_controls=()):
        cohorts, controls = design(st, subset)
        if control_set == "low_exposure":
            controls = [c for c in controls if expo[c] < 7]
        weights_fn = None
        if control_set == "exposure_kernel":
            def weights_fn(coh, base_w=weights):
                tr = [u for m in coh.values() for u in m]
                kw = kernel_weights(expo, expo[tr].mean()); kw[tr] = 1.0
                return kw if base_w is None else base_w * kw
            weights = weights_fn(cohorts)
        controls = [c for c in controls if c not in drop_controls]
        W = wide(df, y)
        if covid_adj:
            # residualize spending on contemporaneous new COVID case rate within state (partial out the Delta wave)
            C = wide(df, "new_case_rate").reindex(W.index)[W.columns]
            b = np.nansum(((W - W.mean(axis=1).values[:, None]) * (C - C.mean(axis=1).values[:, None])).values) / \
                np.nansum(((C - C.mean(axis=1).values[:, None]) ** 2).values)
            W = W - b * C
        ev, post, pre = one_spec(W, cohorts, controls, base=base, weights=weights)
        slope = pretrend_slope(ev)
        pre_far = float(np.mean([ev[e] for e in ev.index if -12 <= e <= -9]))   # weeks outside the anchor window
        p, sd, q_lo, q_hi = ri_pvalue(W, cohorts, controls, post, base=base, weights=weights, weights_fn=weights_fn) if ri else (np.nan, np.nan, np.nan, np.nan)
        specs.append(dict(spec=name, outcome=y, subset=subset, base=str(base)[:10], weighted=weights is not None, control_set=control_set,
                          n_treated=sum(len(m) for m in cohorts.values()), n_control=len(controls),
                          post_att=post, ri_sd=sd, ri_p=p, ci_lo=post - q_hi, ci_hi=post - q_lo, pre_avg=pre, pre_far_avg=pre_far,
                          pre_minus1=float(ev.get(-1, np.nan)), pre_slope=slope, trend_adj_post=linear_trend_adjusted_post(ev, slope)))
        for e, v in ev.items():
            paths.append(dict(spec=name, e=e, att=v))
        print(f"{name:42s} post={post:6.2f} ri_sd={sd:5.2f} p={p:4.2f} pre={pre:6.2f} slope={slope:6.3f}/wk trend_adj={linear_trend_adjusted_post(ev, slope):6.2f}")

    # first stage
    add("claims, g-1 base", "y_claims")
    add("claims, all-programs states", "y_claims", subset="all_programs")
    add("claims, FPUC-only states", "y_claims", subset="fpuc_only")
    # spending, headline grid
    add("spend, g-1 base", "y_spend_all")
    add("spend, pre-period mean base", "y_spend_all", base="premean")
    add("spend, pre-announcement base (May 1)", "y_spend_all", base=ANNOUNCE_BASE)
    add("spend, population-weighted, premean", "y_spend_all", base="premean", weights=pop)
    add("spend, population-weighted, g-1", "y_spend_all", weights=pop)
    add("spend, population-weighted, May 1 base", "y_spend_all", base=ANNOUNCE_BASE, weights=pop)
    add("spend, all-programs states", "y_spend_all", subset="all_programs")
    add("spend, FPUC-only states", "y_spend_all", subset="fpuc_only")
    add("spend, June cohorts only", "y_spend_all", subset="june")
    add("spend, COVID-case adjusted, g-1", "y_spend_all", covid_adj=True)
    add("spend, low-exposure controls (<7 per 100)", "y_spend_all", base="premean", control_set="low_exposure")
    add("spend, exposure-kernel-weighted controls", "y_spend_all", base="premean", control_set="exposure_kernel")
    add("spend, drop CA and NY (late reopeners)", "y_spend_all", base="premean", drop_controls=("CA", "NY"))
    add("spend, premean, population-weighted, low-exposure controls", "y_spend_all", base="premean", weights=pop, control_set="low_exposure")
    add("spend low-income ZIPs, g-1", "y_spend_all_q1")
    add("spend high-income ZIPs, g-1", "y_spend_all_q4")
    add("spend low minus high income ZIPs", "y_gap_q1_q4")
    add("in-person spend, g-1", "y_spend_inperson")
    pd.DataFrame(specs).to_csv(OUT / "state_specs.csv", index=False)
    pd.DataFrame(paths).to_csv(OUT / "state_event.csv", index=False)
    # State-level dose test: each treated state's own premean ATT against its May 29 claims per 100
    cohorts, controls = design(st); W = wide(df, "y_spend_all"); rows = []
    for g, m in cohorts.items():
        for u in m:
            r = att_gt(W, {g: [u]}, controls, base="premean")
            rows.append(dict(state=u, exposure=expo[u], att=r[r.e >= 0].att.mean()))
    dz = pd.DataFrame(rows)
    import statsmodels.formula.api as smf
    fit = smf.ols("att ~ exposure", data=dz).fit(cov_type="HC1")
    dose = dict(slope=fit.params["exposure"], se=fit.bse["exposure"], corr=dz[["att", "exposure"]].corr().iloc[0, 1], n=len(dz),
                low_half_att=dz[dz.exposure <= dz.exposure.median()].att.mean(), high_half_att=dz[dz.exposure > dz.exposure.median()].att.mean())
    pd.Series(dose).to_csv(OUT / "state_dose.csv"); dz.to_csv(OUT / "state_dose_points.csv", index=False)
    print("dose test:", {k: round(v, 3) for k, v in dose.items()})
    # tests against zero and against the implied effect (0.40 lower, 0.67 upper bound), by test inversion plus normal approximation
    from scipy.stats import norm
    S = pd.DataFrame(specs).set_index("spec"); rows = []
    for name in ["spend, pre-period mean base", "spend, low-exposure controls (<7 per 100)", "spend, exposure-kernel-weighted controls", "spend, population-weighted, premean"]:
        r = S.loc[name]; z0 = r.post_att / r.ri_sd; zl = (r.post_att + 0.40) / r.ri_sd; zu = (r.post_att + 0.67) / r.ri_sd
        rows.append(dict(spec=name, est=r.post_att, sd=r.ri_sd, ci_lo=r.ci_lo, ci_hi=r.ci_hi,
                         z_vs_zero=z0, p_vs_zero=2 * norm.sf(abs(z0)), z_vs_implied_low=zl, p_vs_implied_low=2 * norm.sf(abs(zl)),
                         z_vs_implied_high=zu, p_vs_implied_high=2 * norm.sf(abs(zu)),
                         rejects_zero=not (r.ci_lo <= 0 <= r.ci_hi), rejects_implied_low=not (r.ci_lo <= -0.40 <= r.ci_hi),
                         rejects_implied_high=not (r.ci_lo <= -0.67 <= r.ci_hi)))
    pd.DataFrame(rows).to_csv(OUT / "tests_vs_implied.csv", index=False)
    return pd.DataFrame(specs)


if __name__ == "__main__":
    run()
