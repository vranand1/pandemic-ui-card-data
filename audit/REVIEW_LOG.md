# Review log

Independent reviewer: a super-critical applied econometrician persona (referee-2 standard), run as a separate agent
with read access to the project and the papers, and no access to the author's reasoning. Three rounds.

## Round 1 (first draft, Oct 17, 2026): grade C+
Findings: not a replication (microdata not public; different estimand); every spending number cited from the
2021 working paper but attributed to the 2022 P&P; sign of the spending estimate flipped with the base week
(+0.21 to -0.50); population-weighted estimate computed but not reported; 13-day smoothing window; NaN-weight
bug in the weighted estimator; synthetic control uninformative (4-state average vs single-state placebos,
sign reversal by August); power calculation in mismatched units (PCE vs card spending, equal- vs
population-weighted SE); five FPUC-only states pooled with full withdrawals; no control for Delta, child tax
credit, political selection; claims-timing convention unverified.

## Round 2 (rebuilt, Oct 17): grade B
Fixes accepted: reframing, citations, Saturday-value aggregation (section C of tests.py: +0.21 to -0.37 from
that change alone), premean anchor, specification grid, randomization inference (size 5.5% at nominal 5%),
border-county design, corrected power units, synthetic control removed, audit folder.
New findings: comparison states have twice the claim rate (9.3 vs 4.5) and include slow reopeners, and the
headline moves from -0.31 to -0.11 against low-claim comparison states; border population weights triple-count
large counties; the e = -1 event is a retain-side dip, not a treated-side spike; subset randomization used the
full-design null; four prose numbers untraced; county exposure measure wrong for the question; pre-check
language partly tautological under the premean anchor; RI should be called a placebo distribution with
intervals by test inversion.

## Round 3 (all nine items fixed, Oct 17): grade B+, A- conditional on two fixes
Fixes accepted: low-claim and kernel-reweighted comparison sets, state dose test, harmonic-mean pair weights
with reuse discount, e = -1 decomposition, subset-aware permutation, 60 traced claims, exposure-split caveat,
informative pre weeks, test-inversion intervals, pop-share denominator, moving-average assumption stated.
Remaining: (1) "every withdrawal state had a Republican governor" is false (Louisiana); (2) the closing
power paragraph conflated sampling variation with confounding; replace with explicit tests of each estimate
against zero and against the implied effect; (3) kernel weights should be recomputed inside each permutation.

## After round 3
All three applied. Kernel weights now rebuilt per permutation (sd 0.26, skewed null, interval -0.97 to +0.01).
Tests table added (out/tests_vs_implied.csv): no comparison rejects zero or the implied effect. Louisiana
corrected to "23 of the 24". check_post.py: 65 claims traced. Border pre-period slope (+0.37 per week) now stated.

## Round 4 (independent outside referee with the full repository, Oct 17, 2026): grade B- (design B+, code C+)
The referee reran run_all.sh (bit-for-bit match to the shipped outputs and figures), then found five errors in the
estimator code and two wrong explanations in the post. All reproduced by the author and fixed on Oct 17:
1. Kernel-reweighted comparison: the permutation null was not skewed, it was shifted (mean +0.40, skewness
   -0.08). Pseudo-treated states drawn at random sit at the grand-mean claim rate while the kernel concentrates
   pseudo-controls on middle-exposure states, so every draw was biased up. Fix: permute within exposure
   quartiles (stratified_randomization_inference), which centers the null (mean +0.05); the null mean is now
   written to state_specs.csv for every specification. The "skewed" sentences are gone from the post.
2. Population weights: att_gt weighted within cohorts by population but across cohorts by the count of states,
   so Alabama outweighed Florida. Fix: cohort weight = sum of weights of treated states with data. The
   population-weighted estimate moves from -0.41 to -0.56 (premean), -0.58 to -0.62 (g-1), -0.86 to -0.91 (May 1).
3. Anchor switching: add() defaulted to base="g-1", so eight specifications ran on the single-week anchor while
   the post presented them beside the pre-period mean results. Fix: premean is the default everywhere; the
   g-1 rows say so in their names. Under premean the 19 all-program states give -0.19 (was -0.50), the five
   supplement-only states -0.79 (was +0.15), the June cohorts -0.37 (was -0.58). The pre-period gaps quoted for
   high-income ZIP and in-person spending (1.5 to 2.4) were g-1 numbers; the series still fail the pre-trend
   check under premean (slopes of -0.23 and -0.62 log points a week) and are still not used.
4. Trend extrapolation: linear_trend_adjusted_post subtracted slope x (e + 1), which assumes the path is zero at
   e = -1 and is only right for the g-1 anchor. Fix: fit a line with intercept on weeks -8 to -1 and subtract it.
   On a pure 0.1/week trend with no effect the old code left +0.40, the new code leaves 0.000. The headline
   trend-adjusted figure moves from -0.07 to +0.08.
5. COVID adjustment: the slope of spending on cases was estimated with state effects only; it came out positive
   and pushed the estimate the wrong way (-0.48). Fix: two-way (state and week) within transformation; the
   adjusted estimate is -0.30, the same as the unadjusted one. Cases now use the Saturday value, like spending.
6. Minor: all-missing states no longer count in cohort weights or sample sizes (low-income ZIPs -0.65 on
   23 vs 22 states); border pair reuse counted on the full pair table (-1.32 to -1.31); -inf from one county's
   spend_all = -1.0 filtered; DC dropped from power.py; the stale "about -0.7 to +0.6" sentence removed.
7. Audit scripts: check_post.py now formats each CSV value into the quoted text, so a changed output fails the
   check (the old version only tested that a hardcoded string was present); tests.py builds the coverage null
   from the panel with the imposed effect removed, and the OLS check now covers the population-weighted
   estimator (WLS) and the series with missing states.
Also taken from the review: the low-claim comparison now restricts both sides to states under 7 claims per 100
(20 treated vs 10 comparison; +0.08, sd 0.35), so the permutation over those 30 states is symmetric; the
$490 million sentence now states who lost what; the border paragraph no longer says adjacent counties share
the reopening calendar. Not adopted: the referee's statement that the tracker's moving average is documented
as backward-looking (the data dictionary says "7 day moving average" and nothing more; the post keeps its
caveat), and a side figure of -0.025 for the symmetric low-claim design, which does not reproduce (+0.08 by two
independent computations). The referee's CTC-timing point (the +0.3 bump at e = +3 in both designs lines up
with the July 15 child tax credit payment) is now mentioned in the post as an unresolved confounder.

## Staff econometrician sign-off checks (audit/tests.py, size_test.py, check_post.py)
- Estimator bias on simulated staggered panels with heterogeneous dynamic effects: +0.03 (g-1 anchor), -0.01
  (premean), -0.002 (border pairs with shared local shocks).
- Randomization test size under the sharp null: 5.5% at nominal 5% (200 simulations x 200 permutations).
- Spurious pre-trend of 0.1 per week with no effect biases the estimator by +0.9, as expected; the pre-period
  diagnostics reported in the post are the safeguard.
- Independent OLS re-implementation (unit and week fixed effects, cohort by cohort against never-treated states)
  matches the hand-coded estimator to 1e-15 for both outcomes; the stacked pair-by-week regression matches the
  border estimator to 0.01 (cell weighting across truncated cohorts).
- Claims dating verified against Iowa PUA counts (10,055 to 568 across the June 12 end date).
- Cohort assignment verified against NELP dates.
