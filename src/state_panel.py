"""State-week panel: card spending (Saturday value of the 7-day average), continued claims, COVID cases."""
import pandas as pd, numpy as np
from common import *

SP = ["spend_all", "spend_all_q1", "spend_all_q2", "spend_all_q3", "spend_all_q4", "spend_retail_w_grocery", "spend_inperson"]


def load_state():
    st = state_table()
    a = pd.read_csv(RAW / "Affinity_-_State_-_Daily.csv", na_values=".")
    sp = weekly_from_daily(a, "statefips", SP)
    u = pd.read_csv(RAW / "UI_Claims_-_State_-_Weekly.csv", na_values=".")
    u["week"] = pd.to_datetime(dict(year=u.year, month=u.month, day=u.day_endofweek))
    u = u[["statefips", "week", "contclaims_rate_combined", "contclaims_count_combined", "contclaims_rate_regular"]]
    c = pd.read_csv(RAW / "COVID_-_State_-_Daily.csv", na_values=".")
    c["date"] = pd.to_datetime(dict(year=c.year, month=c.month, day=c.day))
    # new_case_rate is already a 7-day rolling figure; take the Saturday value, as for spending (averaging it over
    # the week again would be the 13-day double smoothing the post criticizes)
    c = c[c.date.dt.weekday == 5].rename(columns={"date": "week"})
    cv = c[["statefips", "week", "new_case_rate"]]
    df = sp.merge(u, on=["statefips", "week"], how="left").merge(cv, on=["statefips", "week"], how="left")
    df = df.merge(st[["statefips", "stateabbrev", "state_pop2019", "g", "kind", "treated"]], on="statefips")
    df = df[(df.week >= START) & (df.week <= STOP)].copy()
    for col in SP:
        df["y_" + col] = logpts(df[col])
    df["y_gap_q1_q4"] = df.y_spend_all_q1 - df.y_spend_all_q4
    df["y_claims"] = df.contclaims_rate_combined
    exp = df[df.week == "2021-05-29"].set_index("stateabbrev").contclaims_rate_combined
    df["exposure"] = df.stateabbrev.map(exp)
    return df, st


if __name__ == "__main__":
    df, st = load_state()
    df.to_csv(OUT / "state_panel.csv", index=False)
    s = df.drop_duplicates("stateabbrev")
    print("states", len(s), "treated", int(s.treated.sum()), "all-programs", int((s.kind == "all").sum()),
          "fpuc-only", int((s.kind == "fpuc_only").sum()), "never", int((~s.treated).sum()))
    miss = df.groupby("stateabbrev").spend_all.apply(lambda x: x.isna().all())
    print("spend_all missing entirely:", miss[miss].index.tolist(), "| weeks:", df.week.nunique())
