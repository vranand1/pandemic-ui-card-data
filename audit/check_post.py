"""Every number in the post must trace to an output file. Each claim takes the value from the CSV, formats it
the way the post writes it, and asserts that the formatted text appears in the post. If an output changes, the
formatted text changes and the check fails. (The earlier version only tested that a hardcoded string was
present in the post, which the round-4 referee rightly called theatrical.)"""
import sys, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
post = (ROOT / "post" / "2026-10-17-pandemic-ui-withdrawal-card-data.md").read_text()
S = pd.read_csv(ROOT / "out" / "state_specs.csv").set_index("spec")
Bd = pd.read_csv(ROOT / "out" / "border_specs.csv").set_index("spec")
X = pd.read_csv(ROOT / "out" / "border_extras.csv").iloc[0]
P = pd.read_csv(ROOT / "out" / "power.csv").set_index("design")
M = pd.read_csv(ROOT / "out" / "power_meta.csv", index_col=0).iloc[:, 0]
TV = pd.read_csv(ROOT / "out" / "tests_vs_implied.csv").set_index("spec")
pairs = pd.read_csv(ROOT / "out" / "border_pairs.csv")
D = pd.read_csv(ROOT / "out" / "state_dose.csv", index_col=0).iloc[:, 0]
EV = pd.read_csv(ROOT / "out" / "state_event.csv"); BE = pd.read_csv(ROOT / "out" / "border_event.csv")

# formatters: a = absolute value, m = minus sign only when negative, s = explicit sign, i = integer
a = lambda v, nd=2: f"{abs(v):.{nd}f}"
m = lambda v, nd=2: f"{v:.{nd}f}"
s = lambda v, nd=2: f"{v:+.{nd}f}"
i = lambda v: f"{int(round(v))}"

checks = []
def claim(label, text):
    """text is already built from output values; it must appear verbatim in the post."""
    checks.append((label, text, text in post))

HEAD, POP, POPM, G1, MAY = "spend, pre-period mean base", "spend, population-weighted, premean", "spend, population-weighted, May 1 base", "spend, g-1 base", "spend, pre-announcement base (May 1)"
LOW, KER, ALLP, FPUC, JUNE, COV, Q1, Q4, INP = ("spend, low-exposure states (<7 per 100, both sides)", "spend, exposure-kernel-weighted controls", "spend, all-programs states",
                                                "spend, FPUC-only states", "spend, June cohorts only", "spend, COVID-case adjusted", "spend low-income ZIPs", "spend high-income ZIPs", "in-person spend")
BH, BPOP, BNEP, B500, BG1 = "border, pre-period mean base", "border, population-weighted, premean", "border, population-weighted, no El Paso", "border, population-weighted, both counties under 500k", "border, g-1 base"

# claims (first stage)
claim("claims drop", f"fell by {a(S.loc['claims, g-1 base', 'post_att'])} per 100 workers")
claim("treated exposure", f"{a(M['claims_per_100_treated'], 1)} claims per 100 in the withdrawal states")
claim("claims all-programs", f"The fall is {a(S.loc['claims, all-programs states, g-1', 'post_att'])} in states that ended all programs and {a(S.loc['claims, FPUC-only states, g-1', 'post_att'])} in states that ended only the supplement")
# headline paragraph
claim("headline", f"ran {a(S.loc[HEAD, 'post_att'])} log points (about {a(S.loc[HEAD, 'post_att'], 1)} percent) below")
claim("headline sd", f"placebo standard deviation is {a(S.loc[HEAD, 'ri_sd'])}")
claim("headline ci", f"runs from {s(S.loc[HEAD, 'ci_lo'])} to {s(S.loc[HEAD, 'ci_hi'])}")
claim("headline p", f"under no effect is {m(S.loc[HEAD, 'ri_p'])}")
claim("range", f"ranges from {m(S.loc[ALLP, 'post_att'], 1)} to {m(S.loc[POPM, 'post_att'], 1)}")
claim("g-1", f"{m(S.loc[G1, 'post_att'])} anchoring on the single week")
claim("May 1", f"{m(S.loc[MAY, 'post_att'])} anchoring on May 1")
claim("pop range", f"{m(S.loc[POP, 'post_att'])} to {m(S.loc[POPM, 'post_att'])} weighting states by population")
claim("all programs", f"{m(S.loc[ALLP, 'post_att'])} in the 19 states that ended all programs")
claim("june", f"{m(S.loc[JUNE, 'post_att'])} in the June cohorts")
claim("covid", f"{m(S.loc[COV, 'post_att'])} after partialling out")
claim("q1", f"{m(S.loc[Q1, 'post_att'])} in the lowest-income ZIP codes (standard deviation {a(S.loc[Q1, 'ri_sd'])})")
claim("fpuc", f"show {m(S.loc[FPUC, 'post_att'])} with a standard deviation of {a(S.loc[FPUC, 'ri_sd'])}")
claim("pop detail", f"{m(S.loc[POP, 'post_att'])} with an interval from {s(S.loc[POP, 'ci_lo'])} to {s(S.loc[POP, 'ci_hi'])} and a two-sided placebo p-value of {m(S.loc[POP, 'ri_p'])}")
# comparison group paragraph
claim("exposure gap", f"{a(M['claims_per_100_control'], 1)} against {a(M['claims_per_100_treated'], 1)} per 100")
claim("low exposure", f"keeps {i(S.loc[LOW, 'n_treated'])} withdrawal states and {i(S.loc[LOW, 'n_control'])} comparison states, moves the estimate to {s(S.loc[LOW, 'post_att'])} (standard deviation {a(S.loc[LOW, 'ri_sd'])}, interval {s(S.loc[LOW, 'ci_lo'])} to {s(S.loc[LOW, 'ci_hi'])})")
claim("kernel", f"gives {m(S.loc[KER, 'post_att'])} ({a(S.loc[KER, 'ri_sd'])}, interval {s(S.loc[KER, 'ci_lo'])} to {s(S.loc[KER, 'ci_hi'])})")
claim("drop CA NY", f"New York gives {m(S.loc['spend, drop CA and NY (late reopeners)', 'post_att'])}")
claim("set range", f"runs from {s(S.loc[LOW, 'post_att'], 1)} to {m(S.loc[POPM, 'post_att'], 1)} depending on the comparison set")
claim("matched downside", f"reach about {m(S.loc[KER, 'ci_lo'], 1)} on the downside")
# dose test
claim("dose slope", f"slope of {m(D['slope'])} log points per claim per 100 (standard error {a(D['se'])})")
claim("dose halves", f"averaged {m(D['high_half_att'])} and the less exposed half {m(D['low_half_att'])}")
# pre-period checks
claim("pre far", f"Those average {s(S.loc[HEAD, 'pre_far_avg'], 1)} and {s(S.loc[HEAD, 'pre_minus1'])} log points")
claim("pre slope", f"slope is {m(S.loc[HEAD, 'pre_slope'])} log points a week")
claim("trend adj", f"moves {m(S.loc[HEAD, 'post_att'])} to {s(S.loc[HEAD, 'trend_adj_post'])}")
claim("failing slopes", f"pre-period slopes of {m(S.loc[Q4, 'pre_slope'])} and {m(S.loc[INP, 'pre_slope'])} log points a week")
claim("failing e-1", f"swings of {m(S.loc[Q4, 'pre_minus1'], 1)} log points in the week before")
assert round(S.loc[Q4, 'pre_minus1'], 1) == round(S.loc[INP, 'pre_minus1'], 1), "the two failing series no longer share a week -1 swing; reword"
claim("in-person", f"would give {m(S.loc[INP, 'post_att'], 1)} with a small p-value")
# border
claim("n pairs", f"{len(pairs)} pairs on {pairs.segment.nunique()} state borders")
claim("SC-NC", f"North Carolina ({(pairs.segment == 'SC-NC').sum()} pairs)")
claim("IA-IL", f"Iowa and Illinois ({(pairs.segment == 'IA-IL').sum()})")
claim("border", f"fell {a(Bd.loc[BH, 'post_att'])} log points relative to the retain side (standard deviation {a(Bd.loc[BH, 'ri_sd'])}, p = {m(Bd.loc[BH, 'ri_p'])}, interval {m(Bd.loc[BH, 'ci_lo'], 1)} to {s(Bd.loc[BH, 'ci_hi'], 1)})")
claim("dd median", f"median pair fell {a(X.dd_median)} log points and {i(100 * X.dd_share_negative)} percent of pairs fell")
claim("loo", f"between {m(X.loo_max, 1)} and {m(X.loo_min, 1)}")
claim("border pop", f"gives {m(Bd.loc[BPOP, 'post_att'])} (p = {m(Bd.loc[BPOP, 'ri_p'])})")
claim("no el paso", f"({m(Bd.loc[BNEP, 'post_att'])}, p = {m(Bd.loc[BNEP, 'ri_p'])})")
claim("under 500k", f"({m(Bd.loc[B500, 'post_att'])}, p = {m(Bd.loc[B500, 'ri_p'])})")
claim("dd sd", f"standard deviation of {a(X.dd_sd, 1)} log points")
claim("border pre range", f"between {m(Bd.loc[BH, 'pre_min'], 1)} and {s(Bd.loc[BH, 'pre_max'], 1)} with a slope of {s(Bd.loc[BH, 'pre_slope'])} log points a week")
claim("e-1 control dip", f"{i(abs(X.e_minus1_control_dev))} log point dip on the retain side")
claim("border g-1", f"{m(Bd.loc[BG1, 'post_att'], 0)} log point \"effect\" with p = {m(Bd.loc[BG1, 'ri_p'])}")
claim("exposure n", f"{i(X.n_pairs_with_exposure)} of the {len(pairs)} pairs")
claim("exposure split", f"gives {s(Bd.loc['border, high-exposure treated counties', 'post_att'], 1)} log points for the more exposed counties and {m(Bd.loc['border, low-exposure treated counties', 'post_att'], 1)} for the less exposed")
e3s = EV[(EV.spec == HEAD) & (EV.e == 3)].att.iloc[0]; e3b = BE[(BE.spec == BH) & (BE.e == 3)].att.iloc[0]
assert round(e3s, 1) == round(e3b, 1), "state and border week +3 bumps no longer round alike; reword"
claim("ctc bump", f"bump of {s(e3s, 1)} log points in event week +3")
# power
claim("recipients", f"About {m(M['recipients_may29'] / 1e6)} million people")
claim("lost per week", f"{i(round(M['lost_per_week_bn'] * 1000, -1))} million a week")
claim("half lost supplement", "half of those claimants lost only"); assert abs(M["share_lost_only_supplement"] - 0.5) < 0.03, M["share_lost_only_supplement"]
claim("fpuc-only share", f"who were {i(100 * M['share_in_fpuc_only_states'])} percent of the total")
claim("cardable weekly", f"{i(M['weekly_treated_cardable_bn'])} billion a week")
claim("pop share", f"{i(100 * M['treated_pop_share'])} percent population share")
claim("implied cardable", f"that is {m(M['implied_pct_cardable'])} percent")
claim("implied pce", f"it is {m(M['implied_pct_pce'])} percent")
claim("wp 2bn", f"implies {m(100 * (2.0 / 7) / M['weekly_treated_cardable_bn'])} percent")
claim("mde state", f"about {m(P.loc['state, pre-period mean base', 'mde_80'])} to {m(P.loc['state, population-weighted, premean', 'mde_80'])} percent")
claim("mde border", f"about {m(P.loc['border, population-weighted, premean', 'mde_80'], 1)} to {i(P.loc['border, pre-period mean base', 'mde_80'])} percent")
# tests table
def flag(row, col):
    if col == "rejects_zero" and row[col] and S.loc[row.name, "ri_p"] > 0.05:
        return "Barely"
    return "Yes" if row[col] else "No"
for spec, lab in [(HEAD, "All 24 comparison states"), (POP, "Population-weighted"), (LOW, "Low-claim states only (20 vs 10)"), (KER, "Reweighted to the treated claim rate")]:
    r = TV.loc[spec]
    est = s(r.est) if spec == LOW else m(r.est)
    claim(f"table {lab}", f"| {lab} | {est} | {s(r.ci_lo)} to {s(r.ci_hi)} | {flag(r, 'rejects_zero')} | {flag(r, 'rejects_implied_low')} | {flag(r, 'rejects_implied_high')} |")
claim("table p", f"two-sided placebo p-value is {m(S.loc[POP, 'ri_p'])}")
# summary lines (FAQ, bottom line, quick answers)
claim("faq headline", f"about {a(S.loc[HEAD, 'post_att'], 1)} log points lower, and {a(S.loc[POP, 'post_att'], 1)} lower when states are weighted")
claim("faq border", f"fell about {a(Bd.loc[BH, 'post_att'], 1)} log points relative to the retain side, {a(Bd.loc[BPOP, 'post_att'], 1)} when pairs are weighted")
claim("faq mde", f"about {m(P.loc['state, pre-period mean base', 'mde_80'])} percent, larger than")
claim("bottom line", f"spent {a(S.loc[HEAD, 'post_att'], 1)} to {a(S.loc[POPM, 'post_att'], 1)} percent less after the cut")
claim("quick range", f"run from {s(S.loc[LOW, 'post_att'], 1)} to {m(S.loc[POPM, 'post_att'], 1)} log points depending on the comparison states")
claim("quick border", f"estimate is {m(Bd.loc[BH, 'post_att'], 1)} to {m(Bd.loc[BPOP, 'post_att'], 1)} log points with wide intervals")
# correction note (corrected values only; the old values are history)
claim("corr pop", f"corrected {m(S.loc[POP, 'post_att'])})")
claim("corr allp", f"corrected {m(S.loc[ALLP, 'post_att'])};")
claim("corr fpuc", f"corrected {m(S.loc[FPUC, 'post_att'])};")
claim("corr june", f"corrected {m(S.loc[JUNE, 'post_att'])})")
claim("corr trend", f"corrected {s(S.loc[HEAD, 'trend_adj_post'])})")
claim("corr covid", f"corrected {m(S.loc[COV, 'post_att'])})")
claim("corr kernel", f"corrected {s(S.loc[KER, 'ci_lo'])} to {s(S.loc[KER, 'ci_hi'])}")
claim("corr low", f"corrected {s(S.loc[LOW, 'post_att'])} for {i(S.loc[LOW, 'n_treated'])} against {i(S.loc[LOW, 'n_control'])}")
# the null of every placebo distribution should be centered (the round-4 kernel bug would show here)
off = S[S.null_mean.abs() > 0.1]
assert off.empty, f"placebo null not centered: {off.null_mean.to_dict()}"

bad = [c for c in checks if not c[2]]
for lab, text, ok in checks:
    print(("OK   " if ok else "MISS ") + f"{lab:20s} '{text}'")
print(f"\n{len(checks) - len(bad)}/{len(checks)} claims traced; placebo null means all within 0.1 of zero (max |mean| = {S.null_mean.abs().max():.3f})")
sys.exit(1 if bad else 0)
