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
