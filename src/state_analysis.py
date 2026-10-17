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


def one_spec(W, cohorts, controls, base="premean", weights=None):
    r = att_gt(W, cohorts, controls, base=base, weights=weights)
    ev, post, pre = aggregate(r)
    return ev, post, pre


def ri_pvalue(W, cohorts, controls, post, base="premean", weights=None, B=B_RI, seed=11, weights_fn=None, strata=None):
    """Placebo distribution: reassign cohorts across the states in the design, recompute the statistic.
    Returns p-value, sd, the 2.5 / 97.5 percentiles of the null (test-inversion interval: est - q97.5, est - q2.5),
    and the null mean (should sit near zero; it is reported so a shifted null cannot hide).
    strata: permute within these strata (used when the estimator conditions on exposure)."""
    units = [u for u in list(W.index) if u in controls or any(u in m for m in cohorts.values())]
    sizes = {g: len(m) for g, m in cohorts.items()}
    def stat(coh, ctl):
        w = weights_fn(coh) if weights_fn is not None else weights     # weights that depend on assignment are rebuilt per draw
        return one_spec(W, coh, ctl, base=base, weights=w)[1]
    if strata is None:
        null = randomization_inference(stat, units, sizes, B=B, seed=seed)
    else:
        null = stratified_randomization_inference(stat, cohorts, controls, strata, B=B, seed=seed)
    p = float((np.abs(null) >= abs(post)).mean())
    return p, float(np.nanstd(null)), float(np.nanquantile(null, .025)), float(np.nanquantile(null, .975)), float(np.nanmean(null))


def run():
    df, st = load_state()
    st = st[st.stateabbrev != "DC"]          # no card data; keep the sample honest
    df = df[df.stateabbrev != "DC"]
    pop = st.set_index("stateabbrev").state_pop2019.astype(float)
    specs, paths = [], []

    expo = df.drop_duplicates("stateabbrev").set_index("stateabbrev").exposure

    # exposure strata for the designs that condition on the May 29 claim rate (quartiles over the 48 states)
    strata_all = pd.Series(pd.qcut(expo, 4, labels=False), index=expo.index)

    def add(name, y, subset="all_treated", base="premean", weights=None, ri=True, covid_adj=False, control_set="all", drop_controls=()):
        """Every specification is anchored on the pre-period mean (base='premean') unless its name says otherwise.
        control_set: 'all'; 'low_exposure' keeps treated AND comparison states with May 29 claims under 7 per 100
        (symmetric, so the permutation test over those states is exact); 'exposure_kernel' reweights comparison
        states toward the treated claim-rate mean and permutes within exposure quartiles."""
        W = wide(df, y)
        has = set(W.index[W.notna().any(axis=1)])                     # states with any data for this series
        cohorts, controls = design(st[st.stateabbrev.isin(has)], subset)
        strata = None
        if control_set == "low_exposure":
            cohorts = {g: [u for u in m if expo[u] < 7] for g, m in cohorts.items()}
            cohorts = {g: m for g, m in cohorts.items() if m}
            controls = [c for c in controls if expo[c] < 7]
        weights_fn = None
        if control_set == "exposure_kernel":
            def weights_fn(coh, base_w=weights):
                tr = [u for m in coh.values() for u in m]
                kw = kernel_weights(expo, expo[tr].mean()); kw[tr] = 1.0
                return kw if base_w is None else base_w * kw
            weights = weights_fn(cohorts)
            strata = strata_all
        controls = [c for c in controls if c not in drop_controls]
        if covid_adj:
            # partial out the contemporaneous new COVID case rate with state AND week fixed effects (two-way within
            # transformation). Round-4 fix: with state effects alone the slope was positive, because both spending and
            # Delta cases rose from spring to late summer, and the adjustment pushed the estimate the wrong way.
            C = wide(df, "new_case_rate").reindex(W.index)[W.columns]
            def tw(X):
                X = X - X.mean(axis=1).values[:, None]
                return X - X.mean(axis=0).values[None, :]
            Wt, Ct = tw(W), tw(C)
            b = np.nansum((Wt * Ct).values) / np.nansum((Ct ** 2).values)
            W = W - b * C
            print(f"   COVID slope (state and week effects): {b:+.6f} log points per new case per 100,000")
        ev, post, pre = one_spec(W, cohorts, controls, base=base, weights=weights)
        slope = pretrend_slope(ev)
        pre_far = float(np.mean([ev[e] for e in ev.index if -12 <= e <= -9]))   # weeks outside the anchor window
        p, sd, q_lo, q_hi, null_mean = ri_pvalue(W, cohorts, controls, post, base=base, weights=weights, weights_fn=weights_fn, strata=strata) if ri else (np.nan,) * 5
        specs.append(dict(spec=name, outcome=y, subset=subset, base=str(base)[:10], weighted=weights is not None, control_set=control_set,
                          n_treated=sum(len(m) for m in cohorts.values()), n_control=len(controls),
                          post_att=post, ri_sd=sd, ri_p=p, ci_lo=post - q_hi, ci_hi=post - q_lo, null_mean=null_mean, pre_avg=pre, pre_far_avg=pre_far,
                          pre_minus1=float(ev.get(-1, np.nan)), pre_slope=slope, trend_adj_post=linear_trend_adjusted_post(ev)))
        for e, v in ev.items():
            paths.append(dict(spec=name, e=e, att=v))
        print(f"{name:46s} post={post:6.2f} ri_sd={sd:5.2f} p={p:4.2f} null_mean={null_mean:5.2f} pre={pre:6.2f} slope={slope:6.3f}/wk trend_adj={linear_trend_adjusted_post(ev):6.2f}")

    # first stage (mechanical drop in claims at e = 0; anchored on the week before withdrawal, as labeled)
    add("claims, g-1 base", "y_claims", base="g-1")
    add("claims, all-programs states, g-1", "y_claims", subset="all_programs", base="g-1")
    add("claims, FPUC-only states, g-1", "y_claims", subset="fpuc_only", base="g-1")
    # spending, headline grid (premean unless the name says otherwise)
    add("spend, pre-period mean base", "y_spend_all")
    add("spend, g-1 base", "y_spend_all", base="g-1")
    add("spend, pre-announcement base (May 1)", "y_spend_all", base=ANNOUNCE_BASE)
    add("spend, population-weighted, premean", "y_spend_all", weights=pop)
    add("spend, population-weighted, g-1", "y_spend_all", base="g-1", weights=pop)
    add("spend, population-weighted, May 1 base", "y_spend_all", base=ANNOUNCE_BASE, weights=pop)
    add("spend, all-programs states", "y_spend_all", subset="all_programs")
    add("spend, FPUC-only states", "y_spend_all", subset="fpuc_only")
    add("spend, June cohorts only", "y_spend_all", subset="june")
    add("spend, COVID-case adjusted", "y_spend_all", covid_adj=True)
    add("spend, low-exposure states (<7 per 100, both sides)", "y_spend_all", control_set="low_exposure")
    add("spend, exposure-kernel-weighted controls", "y_spend_all", control_set="exposure_kernel")
    add("spend, drop CA and NY (late reopeners)", "y_spend_all", drop_controls=("CA", "NY"))
    add("spend, population-weighted, low-exposure states", "y_spend_all", weights=pop, control_set="low_exposure")
    add("spend low-income ZIPs", "y_spend_all_q1")
    add("spend high-income ZIPs", "y_spend_all_q4")
    add("spend low minus high income ZIPs", "y_gap_q1_q4")
    add("in-person spend", "y_spend_inperson")
    add("spend low-income ZIPs, low-exposure states", "y_spend_all_q1", control_set="low_exposure")
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
    for name in ["spend, pre-period mean base", "spend, low-exposure states (<7 per 100, both sides)", "spend, exposure-kernel-weighted controls", "spend, population-weighted, premean"]:
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
