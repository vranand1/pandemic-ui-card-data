"""Figures for the post. Event-time bands are 2.5 and 97.5 percentiles of the randomization distribution
(treatment reassigned across states), so they answer: how large would these paths be if the policy did nothing."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import *
from state_panel import load_state
from state_analysis import wide, design
import border as Bd

BG, FG, MUTED, BLUE, ORANGE, GREY, GREEN = "#181818", "#e5e7eb", "#9ca3af", "#79b8ff", "#f59e0b", "#6b7280", "#34d399"
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": FG,
                     "axes.labelcolor": FG, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GREY,
                     "font.size": 10, "axes.titlesize": 11})


def ri_paths_state(W, st, y_units, B=1000, seed=11, base="premean"):
    cohorts, controls = design(st)
    units = [u for u in W.index]
    sizes = {g: len(m) for g, m in cohorts.items()}
    def stat(coh, ctl):
        return aggregate(att_gt(W, coh, ctl, base=base))[0]
    rng = np.random.default_rng(seed); paths = []
    for _ in range(B):
        perm = list(rng.permutation(units)); coh = {}; i = 0
        for g, n in sizes.items():
            coh[g] = perm[i:i + n]; i += n
        paths.append(stat(coh, perm[i:]))
    return pd.concat(paths, axis=1)


def main():
    df, st = load_state(); st = st[st.stateabbrev != "DC"]; df = df[df.stateabbrev != "DC"]
    cohorts, controls = design(st)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    for ax, (y, title, base) in zip(axes, [("y_claims", "Continued UI claims per 100 in labor force", "g-1"),
                                           ("y_spend_all", "Card spending, log points (about percent)", "premean")]):
        W = wide(df, y)
        ev = aggregate(att_gt(W, cohorts, controls, base=base))[0]
        P = ri_paths_state(W, st, None, base=base)
        lo, hi = P.quantile(.025, axis=1).reindex(ev.index), P.quantile(.975, axis=1).reindex(ev.index)
        ax.fill_between(ev.index, lo, hi, color=GREY, alpha=0.3, lw=0, label="95% range if the policy did nothing (placebo reassignment)")
        ax.axhline(0, color=GREY, lw=.8); ax.axvline(-0.5, color=FG, lw=.8, ls=":")
        ax.plot(ev.index, ev.values, color=BLUE, lw=2, marker="o", ms=3.5, label="Estimate (24 withdrawal vs 24 comparison states)")
        ax.set_title(title); ax.set_xlabel("Weeks since federal benefits ended"); ax.grid(alpha=.12)
    axes[1].axhspan(-0.67, -0.38, color=ORANGE, alpha=.18, lw=0); axes[1].text(-11.5, -0.67 - 0.25, "Drop implied by Coombs et al.", color=ORANGE, fontsize=8)
    axes[0].legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.text(0.01, -0.03, "Spending anchored to the average of weeks -8 to -2 before withdrawal; claims anchored to week -1. Data: Opportunity Insights Economic Tracker (Affinity Solutions card data; DOL claims).", fontsize=7.5, color=MUTED)
    fig.tight_layout(); fig.savefig(FIG / "ui-withdrawal-state-event-study.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Specification chart
    sp = pd.read_csv(OUT / "state_specs.csv"); bd = pd.read_csv(OUT / "border_specs.csv")
    keep_s = ["spend, pre-period mean base", "spend, g-1 base", "spend, pre-announcement base (May 1)", "spend, population-weighted, premean",
              "spend, all-programs states", "spend, June cohorts only", "spend, COVID-case adjusted", "spend low-income ZIPs",
              "spend, drop CA and NY (late reopeners)", "spend, low-exposure states (<7 per 100, both sides)", "spend, exposure-kernel-weighted controls"]
    keep_b = ["border, pre-period mean base", "border, population-weighted, premean", "border, population-weighted, no El Paso",
              "border, all-programs states only", "border, drop largest segment", "border, May 1 base"]
    nice = {"spend, pre-period mean base": "State: all 24 comparison states", "spend, g-1 base": "State: anchor on week before withdrawal",
            "spend, pre-announcement base (May 1)": "State: anchor on May 1", "spend, population-weighted, premean": "State: population-weighted",
            "spend, all-programs states": "State: 19 all-program states only", "spend, June cohorts only": "State: June cohorts only",
            "spend, COVID-case adjusted": "State: COVID case rate partialled out", "spend low-income ZIPs": "State: lowest-income ZIP codes",
            "spend, drop CA and NY (late reopeners)": "State: drop CA and NY", "spend, low-exposure states (<7 per 100, both sides)": "State: low-claim states only (20 vs 10)",
            "spend, exposure-kernel-weighted controls": "State: comparison states reweighted to match claim rate",
            "border, pre-period mean base": "Border: 140 pairs, equal weights", "border, population-weighted, premean": "Border: population-weighted",
            "border, population-weighted, no El Paso": "Border: population-weighted, no El Paso", "border, all-programs states only": "Border: all-program states only",
            "border, drop largest segment": "Border: drop SC-NC border", "border, May 1 base": "Border: anchor on May 1"}
    rows = [(nice[r.spec], r.post_att, r.ci_lo, r.ci_hi, BLUE) for r in sp[sp.spec.isin(keep_s)].itertuples()]
    rows += [(nice[r.spec], r.post_att, r.ci_lo, r.ci_hi, GREEN) for r in bd[bd.spec.isin(keep_b)].itertuples()]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    for i, (lab, b, lo, hi, c) in enumerate(rows[::-1]):
        ax.errorbar(b, i, xerr=[[b - lo], [hi - b]], fmt="o", color=c, ms=5, capsize=3, lw=1.2)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8)
    ax.axvline(0, color=GREY, lw=.8); ax.axvspan(-0.67, -0.38, color=ORANGE, alpha=.18, lw=0)
    ax.text(-0.52, len(rows) - 0.3, "implied by\nCoombs et al.", color=ORANGE, fontsize=8, ha="center")
    ax.set_xlabel("Effect on card spending, log points (approximate 95% interval from the placebo distribution)"); ax.grid(axis="x", alpha=.12)
    fig.text(0.01, -0.02, "All rows anchored to the average of weeks -8 to -2 before withdrawal unless the label says otherwise.", fontsize=7.5, color=MUTED)
    fig.tight_layout(); fig.savefig(FIG / "ui-withdrawal-specifications.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Border event path
    W, geo, expo = Bd.load_counties(); adj = Bd.adjacency(); pr = Bd.build_pairs(st, W, geo, adj)
    ev, post, pre = Bd.pair_event(W, pr, base="premean")
    rng = np.random.default_rng(5); sizes = st[st.treated].groupby("g").size(); base_states = list(st.stateabbrev); paths = []
    for _ in range(600):
        perm = list(rng.permutation(base_states)); i = 0; fake = st.copy(); fake["g"] = pd.NaT
        for g, n in sizes.items():
            fake.loc[fake.stateabbrev.isin(perm[i:i + n]), "g"] = g; i += n
        fake["treated"] = fake.g.notna(); p2 = Bd.build_pairs(fake, W, geo, adj)
        if len(p2):
            paths.append(Bd.pair_event(W, p2, base="premean")[0])
    P = pd.concat(paths, axis=1); lo, hi = P.quantile(.025, axis=1).reindex(ev.index), P.quantile(.975, axis=1).reindex(ev.index)
    fig, ax = plt.subplots(figsize=(7.5, 3.5))
    ax.fill_between(ev.index, lo, hi, color=GREY, alpha=.3, lw=0, label="95% range if the policy did nothing (placebo reassignment)")
    ax.axhline(0, color=GREY, lw=.8); ax.axvline(-0.5, color=FG, lw=.8, ls=":")
    ax.plot(ev.index, ev.values, color=GREEN, lw=2, marker="o", ms=3.5, label="140 border county pairs, 31 state borders")
    ax.axhspan(-0.67, -0.38, color=ORANGE, alpha=.18, lw=0)
    ax.set_title("Border counties: card spending, withdrawal side minus retain side (log points)")
    ax.set_xlabel("Weeks since federal benefits ended"); ax.legend(frameon=False, fontsize=8, loc="lower left"); ax.grid(alpha=.12)
    fig.tight_layout(); fig.savefig(FIG / "ui-withdrawal-border.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    # Power chart
    pw = pd.read_csv(OUT / "power.csv"); meta = pd.read_csv(OUT / "power_meta.csv", index_col=0).iloc[:, 0]
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    labels = ["Implied by Coombs et al.\n(share of card-type spending)", "Implied by Coombs et al.\n(share of all consumption)",
              "Smallest detectable effect,\nstate design (80% power)", "Smallest detectable effect,\nborder design (80% power)"]
    vals = [meta["implied_pct_cardable"], meta["implied_pct_pce"], pw.loc[0, "mde_80"], pw.loc[2, "mde_80"]]
    cols = [ORANGE, ORANGE, BLUE, GREEN]
    ax.barh(labels, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(v + 0.03, i, f"{v:.2f}%", va="center", color=FG)
    ax.invert_yaxis(); ax.set_xlim(0, max(vals) * 1.2); ax.set_xlabel("Percent of weekly spending in withdrawal states"); ax.grid(axis="x", alpha=.12)
    fig.tight_layout(); fig.savefig(FIG / "ui-withdrawal-power.png", dpi=180, bbox_inches="tight"); plt.close(fig)
    print("figures written")


if __name__ == "__main__":
    main()
