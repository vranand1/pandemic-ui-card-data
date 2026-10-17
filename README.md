# Early withdrawal of pandemic unemployment benefits: what public card data can and can't see

An aggregate test of the spending effects in Coombs, Dube, Jahnke, Kluender, Naidu and Stepner,
"Early Withdrawal of Pandemic Unemployment Insurance" (working paper, Aug 2021; employment and earnings
results published in AEA Papers and Proceedings 112, 2022), using public state- and county-level card data.

## Question
Coombs et al. find, in bank-account data on low-income benefit recipients, that ending federal pandemic
unemployment benefits early in 2021 cut their spending by about $145 a week (about 20%). Do public card
spending data show that drop at the level of states and counties, and if not, what effect could they detect?

## Design
- Panel: 48 states (DC has no card data; IN and MD dropped because courts restored benefits) x 27 weeks,
  Mar 6 to Sep 4, 2021. Weekly value = the Saturday observation of OI's 7-day moving average.
- Treatment: week containing the first day without federal benefits. 24 treated states in six cohorts
  (Jun 19 to Aug 7); 19 ended all programs, 5 ended only the $300 supplement. 24 never-treated states (plus DC, no card data).
- State estimator: Callaway and Sant'Anna style ATT(g,t) with never-treated controls; each state anchored
  to its own mean over event weeks -8 to -2 (also reported: g-1 anchor, May 1 anchor).
- Border estimator: 140 adjacent county pairs across 31 state borders (Census adjacency file), treated-side
  minus retain-side spending relative to the same pre-period mean, averaged across pairs.
- Inference: placebo (randomization) distribution from reassigning the (cohort, program-type) labels across states,
  rebuilding border pairs and re-applying the subset rule each draw; 1,000 draws. Intervals by test inversion. Segment cluster bootstrap as a check.
- Power: minimum detectable effect (2.8 x RI sd) against the effect implied by Coombs et al., expressed as a
  share of card-type consumption (PCE less housing, health and financial services) in the withdrawal states.

## Main results (out/state_specs.csv, out/border_specs.csv, out/power.csv)
- Continued claims per 100 in labor force: -1.25 (RI sd 0.30, p < 0.001); -1.34 all-programs states, -0.90 FPUC-only.
- Card spending, state design: -0.31 log points (RI sd 0.27, p = 0.26) against all 24 comparison states; -0.37 to -0.86 across anchors, weights and subsets; -0.11 (sd 0.38) against the 10 low-claim comparison states (placebo test conditional on dropping the 14 high-claim states) and -0.09 (sd 0.26, skewed null, interval -0.97 to +0.01) with comparison states reweighted to the treated claim rate (kernel weights recomputed inside each permutation); tests against zero and against the implied effect in out/tests_vs_implied.csv, none rejects; +0.15 in FPUC-only states. Within-treated dose test: slope -0.12 per claim per 100 (se 0.17).
- Border design: -0.92 (RI sd 0.73, p = 0.20); population-weighted (harmonic-mean pair weights, discounted for reuse) -1.32 (p = 0.01), -1.10 without El Paso, -0.98 with both counties under 500k; the county exposure split is uninformative (wrong measure, 74 pairs).
- Implied effect: 0.38% to 0.67% of weekly spending in withdrawal states. MDE at 80% power: 0.75% (state), 2.0% (border).

## Audit (audit/)
- `tests.py`: Monte Carlo on simulated staggered panels (bias of both estimators, RI coverage, a spurious
  pre-trend case), independent OLS re-implementation (matches hand-coded estimates to 1e-15 for the state
  design; to 0.01 for the border design, which differs by cell weighting), smoothing-window comparison, design checks.
- `size_test.py`: rejection rate of the randomization test under the sharp null.
- `check_post.py`: asserts that 60 numeric claims in the post match the output files (the remaining prose numbers are citations to Coombs et al.).
- `audit_report.txt`: the log from the last run.

## Files
- `get_data.sh`: downloads the Opportunity Insights files and the Census county adjacency file.
- `src/common.py`: treatment dates, estimators, randomization inference.
- `src/state_panel.py`, `src/state_analysis.py`: state panel and specification grid.
- `src/border.py`: county pairs, border estimator, exposure split.
- `src/power.py`: implied effect and minimum detectable effects.
- `src/figs.py`: charts in `fig/`.
- `post/`: the blog post.
- `run_all.sh`: reproduces everything (about 25 minutes; randomization inference is the slow part).

## Data sources
- Opportunity Insights Economic Tracker, https://github.com/OpportunityInsights/EconomicTracker
  (Affinity Solutions card spending by state and county; DOL unemployment claims; policy milestones).
- Census Bureau county adjacency file, https://www2.census.gov/geo/docs/reference/county_adjacency.txt
- NELP, States Canceling CARES Act UI Benefits (Aug 24, 2021), for the South Carolina date and cross-checks.
- BEA NIPA Table 2.3.5 (2021 PCE by major type) for the consumption denominators.
