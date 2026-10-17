"""Minimum detectable effect versus the effect implied by Coombs et al. (2021 WP), in matching units.

Implied effect: recipients in withdrawal states (DOL continued claims, all programs, week ending May 29, 2021)
times the WP's -$145 per recipient-week, divided by weekly 'cardable' consumption in those states.
Cardable consumption: PCE less housing and utilities, health care, and financial services and insurance
(BEA Table 2.3.5, 2021: PCE 16,216; housing+utilities 2,897; health 2,850; financial+insurance 1,247; $bn).
Treated-state share of consumption is proxied by population share (41%).
MDE at 80% power, 5% two-sided: 2.8 x SE, with SE from randomization inference of the matching spec."""
import numpy as np, pandas as pd
from common import *
from state_panel import load_state

PCE_2021, HOUSING, HEALTH, FIN = 16216.0, 2897.0, 2850.0, 1247.0      # $bn, BEA 2021 annual
WP_SPEND_PER_WEEK = 145.0


def run():
    df, st = load_state()
    s = df[(df.week == "2021-05-29") & (df.stateabbrev != "DC")]      # DC is outside the design (no card data)
    tr = s[s.treated]; nv = s[~s.treated]
    recipients = tr.contclaims_count_combined.sum()
    allpop = pd.read_csv(RAW / "GeoIDs_-_State.csv").state_pop2019.sum()      # all 50 states plus DC
    pop_share = tr.state_pop2019.sum() / allpop
    cardable = (PCE_2021 - HOUSING - HEALTH - FIN) * 1e9
    weekly_treated_cardable = cardable * pop_share / 52
    weekly_treated_pce = PCE_2021 * 1e9 * pop_share / 52
    lost = recipients * WP_SPEND_PER_WEEK
    # who lost what on May 29: PUA and PEUC claimants in all-program states lost everything; regular-program
    # claimants everywhere and all claimants in the five supplement-only states lost only the $300 FPUC supplement
    u = pd.read_csv(RAW / "UI_Claims_-_State_-_Weekly.csv", na_values=".")
    u["week"] = pd.to_datetime(dict(year=u.year, month=u.month, day=u.day_endofweek))
    c = u[u.week == "2021-05-29"].merge(st, on="statefips"); c = c[c.treated]
    allp, fp = c[c.kind == "all"], c[c.kind == "fpuc_only"]
    share_only_supplement = (allp.contclaims_count_regular.sum() + fp.contclaims_count_combined.sum()) / c.contclaims_count_combined.sum()
    share_in_fpuc_only_states = fp.contclaims_count_combined.sum() / c.contclaims_count_combined.sum()
    implied_cardable = 100 * lost / weekly_treated_cardable
    implied_pce = 100 * lost / weekly_treated_pce
    specs = pd.read_csv(OUT / "state_specs.csv").set_index("spec")
    bord = pd.read_csv(OUT / "border_specs.csv").set_index("spec")
    rows = []
    for name, sd in [("state, pre-period mean base", specs.loc["spend, pre-period mean base", "ri_sd"]),
                     ("state, population-weighted, premean", specs.loc["spend, population-weighted, premean", "ri_sd"]),
                     ("border, pre-period mean base", bord.loc["border, pre-period mean base", "ri_sd"]),
                     ("border, population-weighted, premean", bord.loc["border, population-weighted, premean", "ri_sd"])]:
        rows.append(dict(design=name, ri_sd=sd, mde_80=2.8 * sd, implied_pct_cardable=implied_cardable,
                         implied_pct_pce=implied_pce, ratio_mde_to_implied=2.8 * sd / implied_cardable))
    out = pd.DataFrame(rows)
    meta = dict(recipients_may29=recipients, treated_pop_share=pop_share, lost_per_week_bn=lost / 1e9,
                weekly_treated_cardable_bn=weekly_treated_cardable / 1e9, implied_pct_cardable=implied_cardable,
                implied_pct_pce=implied_pce, wp_2bn_over_7wk_per_week_bn=2.0 / 7,
                claims_per_100_treated=tr.contclaims_rate_combined.mean(), claims_per_100_control=nv.contclaims_rate_combined.mean(),
                share_lost_only_supplement=share_only_supplement, share_in_fpuc_only_states=share_in_fpuc_only_states)
    out.to_csv(OUT / "power.csv", index=False)
    pd.Series(meta).to_csv(OUT / "power_meta.csv")
    print(pd.Series(meta).round(3).to_string()); print(out.round(3).to_string(index=False))
    return out, meta


if __name__ == "__main__":
    run()
