"""What the Power BI report should show, recomputed in pandas from the CSVs and checked against the Python analysis
(data/cleaned/summary.json). Run from powerbi/:  python tools/expected.py"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CL = os.path.join(os.path.dirname(ROOT), "data", "cleaned")
S = json.load(open(os.path.join(CL, "summary.json")))
cu = pd.read_csv(os.path.join(CL, "customers.csv"))
sq = pd.read_csv(os.path.join(CL, "sequential.csv"))
sg = pd.read_csv(os.path.join(CL, "segments.csv"))
po = pd.read_csv(os.path.join(CL, "policy.csv")).set_index("policy")
aa = pd.read_csv(os.path.join(CL, "aa_test.csv")).iloc[0]
problems = []


def check(label, got, want, tol=1e-9):
    if abs(got - want) > tol:
        problems.append(f"{label}: {got} vs {want}")


arm = cu.groupby("arm")
spend, conv, visit = arm.spend.mean(), arm.conversion.mean(), arm.visit.mean()
NO, MEN, WOM = "No E-Mail", "Mens E-Mail", "Womens E-Mail"
lift = spend[MEN] - spend[NO]
check("Men's email spend lift", lift, S["estimates"]["spend|Mens E-Mail"]["diff"])
check("Men's email spend lift %", lift / spend[NO], S["estimates"]["spend|Mens E-Mail"]["rel"])
check("Men's vs women's", spend[MEN] - spend[WOM], S["head_to_head"]["spend"]["diff"])
day = int(sq[(sq.metric == "spend") & (sq.arm == MEN) & (sq.p_always_valid < 0.05)].day.min())
check("Safe to call day", day, S["first_always_valid_call_day"][MEN])
harmed = sg[sg.status == "harmed"].level.nunique()
small = sg[sg.status == "too small to tell"].level.nunique()
check("Groups harmed", harmed, len({(r["segment"], r["level"]) for r in S["harmed_segments"]}))
check("False alarms usual", aa.naive_false_alarm, S["aa_test"]["naive_false_alarm"])
check("False alarms always-valid", aa.always_valid_false_alarm, S["aa_test"]["always_valid_false_alarm"])


def profit(margin=0.35, cost=0.02, n=100000):
    return ((po.lift_vs_nobody * margin - po.share_emailed * cost) * n).round(0)


pr = profit()
men, tg = po.loc["Men's email to all"], po.loc["Targeted (by cell)"]
be = (men.lift_vs_nobody - tg.lift_vs_nobody) * 0.35 / (men.share_emailed - tg.share_emailed)
names = {NO: "No email", MEN: "Men's email", WOM: "Women's email"}
lines = ["# Expected values", "", "From `tools/expected.py`, recomputed from the CSVs and checked against the Python analysis (`summary.json`): "
         f"**{'all agree' if not problems else 'DISAGREEMENTS: ' + '; '.join(problems)}**.", "",
         "## Page 1: The call", "", "| Card | Expected |", "|---|---:|",
         f"| Spend per customer, men's email vs none | +${lift:.2f} |", f"| As a % of no-email spend | +{lift / spend[NO]:.0%} |",
         f"| Men's vs women's email | +${spend[MEN] - spend[WOM]:.2f} |", f"| Safe to call on day (of 14) | {day} |", f"| Customer groups harmed | {harmed} |",
         "", "| Email | Spend per customer | Visit rate | Purchase rate |", "|---|---:|---:|---:|",
         *[f"| {names[a]} | ${spend[a]:.2f} | {visit[a]:.1%} | {conv[a]:.2%} |" for a in [NO, MEN, WOM]],
         "", "## Page 2: When to stop", "", "| Card | Expected |", "|---|---:|",
         f"| Fake tests 'won', usual p checked daily | {aa.naive_false_alarm:.1%} |",
         f"| Fake tests 'won', always-valid p | {aa.always_valid_false_alarm:.1%} |",
         "", "## Page 3: Who it works for", "", "| Card | Expected |", "|---|---:|",
         f"| Groups harmed | {harmed} |", f"| Groups too small to tell | {small} |",
         "", "## Page 4: The decision (defaults: 35% margin, $0.02 per email, 100,000 customers)", "", "| Option | Extra profit |", "|---|---:|",
         *[f"| {k} | ${v:,.0f} |" for k, v in pr.sort_values(ascending=False).items()],
         "", f"Best option: **{pr.idxmax()}**. Targeting pays above an email cost of **${be:.3f}**."]
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
open(os.path.join(ROOT, "docs", "expected_values.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if problems else 0)
