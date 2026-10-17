"""Summary chart for the top of the post: the four main comparisons, the effect implied by the bank data,
and the smallest effect the state design can reliably detect. All values read from out/."""
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from common import OUT, FIG

SURFACE, INK, INK2, MUTED, GRID = "#181818", "#f0efec", "#c3c2b7", "#8f8e88", "#2c2c2a"
BLUE, AQUA, ORANGE = "#3987e5", "#199e70", "#d95926"      # validated dark-mode categorical slots
FONT = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"


def main():
    S = pd.read_csv(OUT / "state_specs.csv").set_index("spec")
    pw = pd.read_csv(OUT / "power.csv")
    meta = pd.read_csv(OUT / "power_meta.csv", index_col=0).iloc[:, 0]
    mde = pw.loc[0, "mde_80"]
    lo_imp, hi_imp = meta["implied_pct_pce"], meta["implied_pct_cardable"]
    groups = [
        ("Compared with all 24 states that kept benefits", BLUE, [
            ("Every state counts equally", "spend, pre-period mean base"),
            ("States weighted by population", "spend, population-weighted, premean")]),
        ("Compared with states with similar unemployment", AQUA, [
            ("Only states under 7 claims per 100 (20 vs 10)", "spend, low-exposure states (<7 per 100, both sides)"),
            ("Comparison states reweighted to match", "spend, exposure-kernel-weighted controls")]),
    ]
    plt.rcParams.update({"font.family": FONT, "text.color": INK, "axes.edgecolor": GRID})
    fig = plt.figure(figsize=(10, 6.5), dpi=220)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0.37, 0.22, 0.60, 0.48]); ax.set_facecolor(SURFACE)
    xmin, xmax = -1.35, 0.95
    ax.set_xlim(xmin, xmax)

    # rows: group header slots and estimate rows, top to bottom
    y, rows, headers = 0, [], []
    for title, col, items in groups:
        headers.append((y, title)); y += 1
        for lab, spec in items:
            rows.append((y, lab, spec, col)); y += 1
        y += 0.35
    ytop, ybot = -0.6, y - 0.35 - 0.4
    ax.set_ylim(ybot, ytop)

    # zones
    ax.axvspan(-mde, mde, color="#ffffff", alpha=0.07, lw=0, zorder=0)
    ax.axvspan(-hi_imp, -lo_imp, color=ORANGE, alpha=0.24, lw=0, zorder=1)
    for x in (-hi_imp, -lo_imp):
        ax.axvline(x, color=ORANGE, lw=1, alpha=0.9, zorder=1)
    ax.axvline(0, color=MUTED, lw=1, zorder=1)
    ax.set_xticks([-1.0, -0.5, 0, 0.5])
    ax.set_xticklabels(["-1.0%", "-0.5%", "0", "+0.5%"], fontsize=9, color=INK2)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_yticks([]); [s.set_visible(False) for s in ax.spines.values()]
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)

    # zone labels above the plot
    ax.annotate("Drop the bank data imply\n" + f"{lo_imp:.1f}% to {hi_imp:.1f}%", xy=(-(lo_imp + hi_imp) / 2, ytop), xytext=(0, 8),
                textcoords="offset points", ha="center", va="bottom", fontsize=9, color=INK, fontweight="medium", annotation_clip=False)
    ax.annotate(f"Shaded: effects under about {mde:.2f}%,\ntoo small for state data to detect reliably", xy=(mde, ytop), xytext=(-4, 8),
                textcoords="offset points", ha="right", va="bottom", fontsize=8.5, color=INK2, annotation_clip=False)

    # estimates
    for yy, lab, spec, col in rows:
        b, lo, hi = S.loc[spec, ["post_att", "ci_lo", "ci_hi"]]
        ax.plot([lo, hi], [yy, yy], color=col, lw=2.2, solid_capstyle="round", zorder=3)
        ax.scatter([b], [yy], s=95, color=col, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.annotate(f"{b:+.2f}%".replace("+-", "-"), xy=(b, yy), xytext=(0, 9), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9.5, color=INK, fontweight="semibold", zorder=5)
        fig.text(0.36, ax.transData.transform((0, yy))[1] / fig.bbox.height, lab, ha="right", va="center", fontsize=9.5, color=INK2)
    for yy, title in headers:
        fig.text(0.04, ax.transData.transform((0, yy))[1] / fig.bbox.height, title, ha="left", va="center",
                 fontsize=10, color=INK, fontweight="semibold")
    # group key swatches beside headers
    for (yy, title), (_, col, _) in zip(headers, groups):
        yfig = ax.transData.transform((0, yy))[1] / fig.bbox.height
        fig.lines.append(plt.Line2D([0.02, 0.031], [yfig, yfig], color=col, lw=3, transform=fig.transFigure, solid_capstyle="round"))

    fig.text(0.02, 0.96, "Public card data can't settle the question", fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.89, "Change in weekly card spending in the 24 states that ended pandemic unemployment benefits early, eight weeks\n"
             "after the cut, by comparison group. Dots are estimates; lines are approximate 95% intervals from placebo reassignment.",
             fontsize=9.5, color=INK2, va="top", linespacing=1.4)
    fig.text(0.02, 0.125, "Against all states that kept benefits, the estimates sit near what the bank data imply. Against states with similar unemployment\n"
             "there is no drop, and both intervals exclude the top of the implied range. The data cannot say which comparison is right.",
             fontsize=9, color=INK, va="top", linespacing=1.4)
    fig.text(0.02, 0.018, "Estimates in log points, about equal to percent at this size. Data: Opportunity Insights Economic Tracker (Affinity Solutions card data,"
             " DOL claims); Coombs et al. (2021). vranand1.github.io", fontsize=7, color=MUTED, va="bottom")
    fig.savefig(FIG / "ui-withdrawal-summary.png", facecolor=SURFACE, dpi=220)
    plt.close(fig)
    print("summary figure written")


if __name__ == "__main__":
    main()
