"""Fast unit tests for the estimators in src/common.py. No downloads: every test builds its own small panel.

The slow statistical audit (Monte Carlo bias, size and coverage; OLS re-implementation on the real data) lives
in audit/ and runs as part of run_all.sh. These tests pin down exact, known-answer behaviour so a refactor that
changes a number fails in seconds, in CI, on every push.
"""
import numpy as np
import pandas as pd
import pytest

from common import (WEEK, aggregate, att_gt, first_treated_week, kernel_weights, linear_trend_adjusted_post,
                    pretrend_slope, randomization_inference, stratified_randomization_inference, week_end)

WEEKS = pd.date_range("2021-03-06", periods=27, freq="7D")       # Saturdays, as in the real panel


def noise_free_panel(tau=-2.0, seed=0):
    """Units x weeks with unit effects, week effects and a constant effect tau from each cohort's first week.
    Returns W, cohorts, controls. With no noise, any correct DiD estimator returns exactly tau after treatment
    and exactly 0 before it."""
    r = np.random.default_rng(seed)
    units = [f"U{i:02d}" for i in range(20)]
    alpha = r.normal(0, 3, len(units))
    gamma = np.cumsum(r.normal(0, 1, len(WEEKS)))
    Y = alpha[:, None] + gamma[None, :]
    cohorts = {WEEKS[15]: units[:4], WEEKS[17]: units[4:9]}
    for g, members in cohorts.items():
        for u in members:
            Y[units.index(u), WEEKS >= g] += tau
    W = pd.DataFrame(Y, index=units, columns=WEEKS)
    return W, cohorts, units[9:]


# ---------- dates ----------

def test_week_end_maps_to_following_saturday():
    assert week_end("2021-06-16") == pd.Timestamp("2021-06-19")      # Wednesday
    assert week_end("2021-06-19") == pd.Timestamp("2021-06-19")      # Saturday maps to itself


def test_first_treated_week_is_week_of_first_day_without_benefits():
    # benefits end Saturday June 12, so the first day without them (Sunday June 13) falls in the week ending June 19
    assert first_treated_week("2021-06-12") == pd.Timestamp("2021-06-19")
    assert first_treated_week("2021-06-30") == pd.Timestamp("2021-07-03")


# ---------- staggered DiD ----------

@pytest.mark.parametrize("base", ["premean", "g-1", pd.Timestamp("2021-05-01")])
def test_att_gt_recovers_constant_effect_without_noise(base):
    W, cohorts, controls = noise_free_panel(tau=-2.0)
    r = att_gt(W, cohorts, controls, base=base)
    assert np.allclose(r.loc[r.e >= 0, "att"], -2.0)
    assert np.allclose(r.loc[r.e < 0, "att"], 0.0, atol=1e-12)
    _, post, pre = aggregate(r)
    assert post == pytest.approx(-2.0)
    assert pre == pytest.approx(0.0, abs=1e-12)


def test_att_gt_weighted_matches_unweighted_when_effect_is_homogeneous():
    W, cohorts, controls = noise_free_panel(tau=1.5)
    weights = pd.Series(np.linspace(1, 5, len(W)), index=W.index)
    _, post_w, _ = aggregate(att_gt(W, cohorts, controls, weights=weights))
    assert post_w == pytest.approx(1.5)


def test_att_gt_drops_units_with_no_data():
    W, cohorts, controls = noise_free_panel()
    W.loc[controls[0]] = np.nan                                     # a control with no data at all
    W.loc[cohorts[WEEKS[15]][0]] = np.nan                           # a treated unit with no data at all
    r = att_gt(W, cohorts, controls)
    first = r[(r.g == WEEKS[15]) & (r.e == 0)]
    assert first.n.iloc[0] == 3                                     # 4 members, one dropped
    assert np.allclose(r.loc[r.e >= 0, "att"], -2.0)


def test_att_gt_respects_event_window():
    W, cohorts, controls = noise_free_panel()
    r = att_gt(W, cohorts, controls, emin=-3, emax=2)
    assert r.e.min() == -3 and r.e.max() == 2


# ---------- pre-trend tools ----------

def test_pretrend_slope_and_trend_adjustment_on_a_pure_line():
    ev = pd.Series({e: 0.5 * e for e in range(-8, 9)})              # a pre-trend that simply continues
    assert pretrend_slope(ev) == pytest.approx(0.5)
    assert linear_trend_adjusted_post(ev) == pytest.approx(0.0, abs=1e-12)


def test_trend_adjustment_does_not_depend_on_anchor():
    ev = pd.Series({e: 0.3 * e + (2.0 if e >= 0 else 0.0) for e in range(-8, 9)})
    shifted = ev + 7.0
    assert linear_trend_adjusted_post(ev) == pytest.approx(linear_trend_adjusted_post(shifted))
    assert linear_trend_adjusted_post(ev) == pytest.approx(2.0)


def test_kernel_weights_normalised_and_peaked_at_target():
    exposure = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    w = kernel_weights(exposure, target_mean=3.0)
    assert w.mean() == pytest.approx(1.0)
    assert w.idxmax() == 2


# ---------- randomization inference ----------

def test_randomization_inference_keeps_cohort_sizes_and_is_reproducible():
    units = [f"S{i}" for i in range(12)]
    sizes = {WEEKS[15]: 3, WEEKS[17]: 2}
    seen = []

    def stat(cohorts, controls):
        assert {g: len(m) for g, m in cohorts.items()} == sizes
        assert len(controls) == len(units) - 5
        assert set(sum(cohorts.values(), [])) | set(controls) == set(units)
        seen.append(tuple(cohorts[WEEKS[15]]))
        return float(len(seen))

    a = randomization_inference(stat, units, sizes, B=50, seed=3)
    first = seen[:]
    seen.clear()
    b = randomization_inference(stat, units, sizes, B=50, seed=3)
    assert np.array_equal(a, b) and seen == first
    assert len(set(first)) > 1                                      # draws actually vary


def test_stratified_inference_keeps_counts_within_strata():
    cohorts = {WEEKS[15]: ["A1", "B1"], WEEKS[17]: ["A2"]}
    controls = ["A3", "A4", "B2", "B3", "B4"]
    strata = pd.Series({"A1": "a", "A2": "a", "A3": "a", "A4": "a", "B1": "b", "B2": "b", "B3": "b", "B4": "b"})

    def stat(coh, ctl):
        for g, m in coh.items():
            real = cohorts[g]
            for s in "ab":
                assert sum(strata[u] == s for u in m) == sum(strata[u] == s for u in real)
        return 0.0

    draws = stratified_randomization_inference(stat, cohorts, controls, strata, B=40, seed=1)
    assert draws.shape == (40,)
