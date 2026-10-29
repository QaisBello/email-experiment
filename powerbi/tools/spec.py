"""Power BI version of "Send the men's email." (email experiment readout). Run from powerbi/:

    python tools/spec.py        # writes Email_Experiment.pbip and its folders
    python tools/validate.py    # schema and reference checks
    python tools/expected.py    # what the visuals should show, checked against data/cleaned/summary.json

Customer-level metrics (spend, purchase and visit rates, lifts) are computed in DAX from customers.csv. The statistics
that need more than aggregation (Holm-adjusted p-values, always-valid p-values, the A/A simulation, segment intervals
and the holdout-scored sending options) come from src/analyse.py and are loaded as tables. Margin, email cost and list
size are what-if tables built in Power Query, so the profit page works like the sliders in the web readout.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbikit import C, M, build, card, check_sorts, color, lit, slicer, text_box, visual  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "Email_Experiment"
TEAL, AMBER, GREY, INK = "#0F7A73", "#C98A12", "#8A867B", "#14130F"
USD, USD_CHG = "$#,0.00", "+$#,0.00;-$#,0.00;$0.00"


def what_if(column, values_m, fmt, description):
    return dict(description=description, columns=[(column, "double", {"formatString": fmt, "summarizeBy": "none"})], m=f'''
let
    Source = Table.FromList({values_m}, Splitter.SplitByNothing(), {{"{column}"}}),
    Typed = Table.TransformColumnTypes(Source, {{{{"{column}", type number}}}})
in
    Typed''')


TABLES = {
    "Customers": dict(
        file="customers.csv",
        description="One row per customer (64,000), randomly assigned to the men's email, the women's email or no email. "
                    "Outcomes cover the two weeks after the send.",
        columns=[("customer_id", "string", {"isKey": True}), ("arm", "string", {"isHidden": True}),
                 ("recency", "int64", {"summarizeBy": "none"}), ("recency_band", "string", {}), ("history", "double", {"formatString": USD}),
                 ("history_band", "string", {}), ("purchase_history", "string", {}), ("newbie", "string", {}), ("channel", "string", {}),
                 ("zip_code", "string", {}), ("visit", "int64", {"isHidden": True}), ("conversion", "int64", {"isHidden": True}),
                 ("spend", "double", {"isHidden": True, "formatString": USD})]),
    "Arms": dict(
        description="The three groups of the experiment. Email is the display name; Arm Order keeps no email first.",
        columns=[("arm", "string", {"isKey": True, "isHidden": True}), ("Email", "string", {"sortByColumn": "Arm Order"}),
                 ("Arm Order", "int64", {"isHidden": True})],
        m='''
let
    Source = #table(
        type table [arm = text, Email = text, #"Arm Order" = Int64.Type],
        {{"No E-Mail", "No email", 0}, {"Mens E-Mail", "Men's email", 1}, {"Womens E-Mail", "Women's email", 2}}
    )
in
    Source'''),
    "Estimates": dict(
        file="estimates.csv",
        description="Scorecard from the Python analysis: change against no email for every metric and email, 95% intervals, CUPED, "
                    "and p-values adjusted for six comparisons (Holm).",
        columns=[("metric", "string", {"isHidden": True}), ("metric_name", "string", {}), ("role", "string", {}), ("arm", "string", {"isHidden": True}),
                 ("control_mean", "double", {"isHidden": True}), ("treat_mean", "double", {"isHidden": True}),
                 ("diff", "double", {"formatString": "+0.0000;-0.0000;0"}), ("rel", "double", {"formatString": "+0%;-0%;0%"}),
                 ("lo", "double", {"formatString": "+0.0000;-0.0000;0"}), ("hi", "double", {"formatString": "+0.0000;-0.0000;0"}),
                 ("p", "double", {"isHidden": True}), ("cuped_diff", "double", {"isHidden": True}), ("cuped_lo", "double", {"isHidden": True}),
                 ("cuped_hi", "double", {"isHidden": True}), ("variance_reduction", "double", {"formatString": "0.00%"}),
                 ("p_holm", "double", {"formatString": "0.0E+00"}), ("significant", "boolean", {})]),
    "Sequential": dict(
        file="sequential.csv",
        description="The test replayed in 14 daily batches (seeded random arrival order: the data has no timestamps), with the usual "
                    "p-value and the always-valid p-value each day.",
        columns=[("metric", "string", {}), ("arm", "string", {"isHidden": True}), ("day", "int64", {"summarizeBy": "none"}),
                 ("n", "int64", {"isHidden": True}), ("diff", "double", {"isHidden": True}), ("lo", "double", {"isHidden": True}),
                 ("hi", "double", {"isHidden": True}), ("p_naive", "double", {"isHidden": True}), ("p_always_valid", "double", {"isHidden": True})]),
    "Segments": dict(
        file="segments.csv",
        description="Change in spend per customer for every pre-registered customer group, with the guardrail status: ok, harmed "
                    "(whole interval below zero) or too small to tell (interval reaches below -$1).",
        columns=[("segment", "string", {"isHidden": True}), ("level", "string", {"sortByColumn": "level_order"}), ("arm", "string", {"isHidden": True}),
                 ("n", "int64", {"summarizeBy": "none"}), ("share", "double", {"isHidden": True}), ("diff", "double", {"isHidden": True}),
                 ("lo", "double", {"formatString": USD_CHG}), ("hi", "double", {"formatString": USD_CHG}), ("status", "string", {}),
                 ("level_order", "int64", {"isHidden": True})],
        added=[("Group by", "string", {})],
        m_extra='''
            #"Group by" = Table.AddColumn(#"Filtered Rows", "Group by", each Record.FieldOrDefault([purchase_history = "Bought before", history_band = "Last year's spend", recency_band = "Last purchase", newbie = "New or returning", channel = "Channel", zip_code = "Area"], [segment], [segment]), type text)
        ''', m_last="Group by"),
    "Policy": dict(
        file="policy.csv",
        description="Four sending options, chosen on one random half of customers and scored on the other half. Extra spend is per "
                    "customer against sending nothing, with a bootstrap 95% range.",
        columns=[("policy", "string", {"isKey": True}), ("spend_per_customer", "double", {"isHidden": True}),
                 ("lift_vs_nobody", "double", {"formatString": USD_CHG}), ("lo", "double", {"formatString": USD_CHG}),
                 ("hi", "double", {"formatString": USD_CHG}), ("share_emailed", "double", {"formatString": "0%"})]),
    "AA Test": dict(
        file="aa_test.csv",
        description="1,000 fake tests (no email against no email) checked daily for 14 days: how often each p-value raised a false alarm.",
        columns=[("simulations", "int64", {"isHidden": True}), ("days", "int64", {"isHidden": True}),
                 ("naive_false_alarm", "double", {"isHidden": True}), ("always_valid_false_alarm", "double", {"isHidden": True})]),
    "Margin": what_if("Margin", "List.Transform({5..80}, each _ / 100)", "0%", "What-if: gross margin on sales (5% to 80%). Default 35%."),
    "Email Cost": what_if("Email Cost", "List.Transform({0..60}, each _ * 0.005)", "$0.000", "What-if: cost per email sent ($0 to $0.30). Default $0.02."),
    "List Size": what_if("List Size", "List.Transform({1..100}, each _ * 10000)", "#,0", "What-if: customers on the list. Default 100,000."),
}

RELATIONSHIPS = [
    (("Customers", "arm"), ("Arms", "arm"), {}),
    (("Estimates", "arm"), ("Arms", "arm"), {}),
    (("Sequential", "arm"), ("Arms", "arm"), {}),
    (("Segments", "arm"), ("Arms", "arm"), {}),
]

CU, SQ, SG, PO = "Customers", "Sequential", "Segments", "Policy"
NO, MEN, WOM = '"No E-Mail"', '"Mens E-Mail"', '"Womens E-Mail"'
MEASURES = [
    ("Customers Count", CU, "Outcomes", "#,0", "COUNTROWS ( Customers )", "Customers in the current selection."),
    ("Spend per Customer", CU, "Outcomes", USD, "AVERAGE ( Customers[spend] )", "Spend in the two weeks after the send, per customer."),
    ("Purchase Rate", CU, "Outcomes", "0.00%", "AVERAGE ( Customers[conversion] )", "Share of customers who bought."),
    ("Visit Rate", CU, "Outcomes", "0.0%", "AVERAGE ( Customers[visit] )", "Share of customers who visited the site."),
    ("Spend per Customer (No Email)", CU, "Outcomes", USD, f"CALCULATE ( [Spend per Customer], REMOVEFILTERS ( Arms ), Customers[arm] = {NO} )",
     "The no-email group's spend per customer: the baseline every lift is measured against."),
    ("Spend Change vs No Email", CU, "Lift", USD_CHG, "[Spend per Customer] - [Spend per Customer (No Email)]",
     "Spend per customer minus the no-email group's (0 for the no-email group itself)."),
    ("Purchase Rate Change vs No Email", CU, "Lift", "+0.00%;-0.00%;0.00%",
     f"[Purchase Rate] - CALCULATE ( [Purchase Rate], REMOVEFILTERS ( Arms ), Customers[arm] = {NO} )", "Purchase rate minus the no-email group's, in percentage points."),
    ("Men's Email Spend Lift", CU, "Lift", USD_CHG,
     f"CALCULATE ( [Spend per Customer], REMOVEFILTERS ( Arms ), Customers[arm] = {MEN} ) - [Spend per Customer (No Email)]",
     "Extra spend per customer from the men's email."),
    ("Men's Email Spend Lift %", CU, "Lift", "+0%;-0%;0%", "DIVIDE ( [Men's Email Spend Lift], [Spend per Customer (No Email)] )",
     "The same as a percentage of the no-email group's spend."),
    ("Men's vs Women's Email", CU, "Lift", USD_CHG,
     f"CALCULATE ( [Spend per Customer], REMOVEFILTERS ( Arms ), Customers[arm] = {MEN} ) - CALCULATE ( [Spend per Customer], REMOVEFILTERS ( Arms ), Customers[arm] = {WOM} )",
     "How much more the men's email earned per customer than the women's."),
    ("Always-Valid p (Spend)", SQ, "Monitoring", "0.0E+00", 'CALCULATE ( MIN ( Sequential[p_always_valid] ), Sequential[metric] = "spend" )',
     "Always-valid p-value for spend at each day: safe to check daily; call the test once it is below 0.05."),
    ("Usual p (Spend)", SQ, "Monitoring", "0.0E+00", 'CALCULATE ( MIN ( Sequential[p_naive] ), Sequential[metric] = "spend" )',
     "The usual p-value for spend at each day. Checking it daily inflates false alarms."),
    ("Safe to Call Day", SQ, "Monitoring", "0",
     f'CALCULATE ( MIN ( Sequential[day] ), REMOVEFILTERS ( Arms ), Sequential[arm] = {MEN}, Sequential[metric] = "spend", Sequential[p_always_valid] < 0.05 )',
     "First day the men's email spend result could be called with the always-valid p-value."),
    ("False Alarms, Usual p", "AA Test", "Monitoring", "0.0%", "MAX ( 'AA Test'[naive_false_alarm] )",
     "Share of fake (no difference) tests that 'found' a winner when the usual p-value was checked daily."),
    ("False Alarms, Always-Valid p", "AA Test", "Monitoring", "0.0%", "MAX ( 'AA Test'[always_valid_false_alarm] )",
     "The same with the always-valid p-value."),
    ("Segment Spend Change", SG, "Guardrail", USD_CHG, "AVERAGE ( Segments[diff] )", "Change in spend per customer for a group, against no email."),
    ("Groups Harmed", SG, "Guardrail", "0", 'CALCULATE ( DISTINCTCOUNT ( Segments[level] ), Segments[status] = "harmed" ) + 0',
     "Groups where the whole interval is below zero for either email."),
    ("Groups Too Small to Tell", SG, "Guardrail", "0", 'CALCULATE ( DISTINCTCOUNT ( Segments[level] ), Segments[status] = "too small to tell" ) + 0',
     "Groups too small to rule out a loss beyond -$1 per customer."),
    ("Margin Value", "Margin", "What-if", "0%", "SELECTEDVALUE ( Margin[Margin], 0.35 )", "Selected gross margin (35% if none selected)."),
    ("Email Cost Value", "Email Cost", "What-if", "$0.000", "SELECTEDVALUE ( 'Email Cost'[Email Cost], 0.02 )", "Selected cost per email ($0.02 if none selected)."),
    ("List Size Value", "List Size", "What-if", "#,0", "SELECTEDVALUE ( 'List Size'[List Size], 100000 )", "Selected list size (100,000 if none selected)."),
    ("Extra Profit", PO, "Decision", "$#,0",
     "SUMX ( Policy, ( Policy[lift_vs_nobody] * [Margin Value] - Policy[share_emailed] * [Email Cost Value] ) * [List Size Value] )",
     "Profit on the extra sales minus the cost of the emails, against sending nothing."),
    ("Best Option", PO, "Decision", None,
     '''VAR scored = ADDCOLUMNS ( ALL ( Policy[policy] ), "@profit", [Extra Profit] )
RETURN MAXX ( TOPN ( 1, scored, [@profit], DESC ), Policy[policy] )''', "The sending option with the most extra profit at the selected margin, cost and list size."),
    ("Break-Even Email Cost", PO, "Decision", "$0.000",
     '''VAR men = CALCULATE ( SUM ( Policy[lift_vs_nobody] ), Policy[policy] = "Men's email to all" )
VAR tgt = CALCULATE ( SUM ( Policy[lift_vs_nobody] ), Policy[policy] = "Targeted (by cell)" )
VAR menShare = CALCULATE ( SUM ( Policy[share_emailed] ), Policy[policy] = "Men's email to all" )
VAR tgtShare = CALCULATE ( SUM ( Policy[share_emailed] ), Policy[policy] = "Targeted (by cell)" )
RETURN DIVIDE ( ( men - tgt ) * [Margin Value], menShare - tgtShare )''',
     "Email cost above which targeting beats sending the men's email to everyone."),
]

p1, p2, p3, p4 = "call", "stop", "who", "decision"
CARD = dict(y=76, h=96)
cw = (1232 - 4 * 12) // 5
cx = [24 + i * (cw + 12) for i in range(5)]
PAGES = [
    (p1, "The call", [
        text_box(p1, "title", 24, 12, 1232, 52, "Send the men's email. 64,000 customers: men's email, women's email or nothing", 18),
        card(p1, "lift", cx[0], CARD["y"], cw, CARD["h"], M(CU, "Men's Email Spend Lift", "Spend per customer, men's email vs none")),
        card(p1, "liftp", cx[1], CARD["y"], cw, CARD["h"], M(CU, "Men's Email Spend Lift %", "As a % of no-email spend")),
        card(p1, "mvw", cx[2], CARD["y"], cw, CARD["h"], M(CU, "Men's vs Women's Email", "Men's vs women's email")),
        card(p1, "day", cx[3], CARD["y"], cw, CARD["h"], M(SQ, "Safe to Call Day", "Safe to call on day (of 14)")),
        card(p1, "harm", cx[4], CARD["y"], cw, CARD["h"], M(SG, "Groups Harmed", "Customer groups harmed")),
        visual(p1, "spend", "clusteredColumnChart", 24, 184, 600, 300, {"Category": [C("Arms", "Email", "Email")], "Y": [M(CU, "Spend per Customer", "Spend per customer")]},
               "Spend per customer in the two weeks after the send", objects={"dataPoint": [{"properties": {"fill": color(TEAL)}}],
                                                                              "labels": [{"properties": {"show": lit(True)}}]},
               sort=(C("Arms", "Email"), "Ascending"), z=10),
        visual(p1, "rates", "clusteredColumnChart", 640, 184, 616, 300,
               {"Category": [C("Arms", "Email", "Email")], "Y": [M(CU, "Visit Rate", "Visit rate"), M(CU, "Purchase Rate", "Purchase rate")]},
               "Visit and purchase rates", objects={"labels": [{"properties": {"show": lit(True)}}]}, sort=(C("Arms", "Email"), "Ascending"), z=11),
        visual(p1, "score", "tableEx", 24, 496, 1232, 212,
               {"Values": [C("Estimates", "metric_name", "Metric"), C("Arms", "Email", "Email"), C("Estimates", "diff", "Change vs no email"),
                           C("Estimates", "lo", "95% low"), C("Estimates", "hi", "95% high"), C("Estimates", "rel", "% change"),
                           C("Estimates", "p_holm", "p (Holm-adjusted)")]},
               "Scorecard: change against no email (spend in $, rates as proportions)", objects={"total": [{"properties": {"totals": lit(False)}}]}, z=12),
    ]),
    (p2, "When to stop", [
        text_box(p2, "title", 24, 12, 1232, 52, "Checking daily: the usual p-value raises false alarms, the always-valid one doesn't", 18),
        card(p2, "fa1", 24, 76, 400, 96, M("AA Test", "False Alarms, Usual p", "Fake tests 'won', usual p checked daily")),
        card(p2, "fa2", 436, 76, 400, 96, M("AA Test", "False Alarms, Always-Valid p", "Fake tests 'won', always-valid p")),
        card(p2, "day", 848, 76, 408, 96, M(SQ, "Safe to Call Day", "Men's email safe to call on day")),
        visual(p2, "av", "lineChart", 24, 184, 612, 524,
               {"Category": [C(SQ, "day", "Day")], "Y": [M(SQ, "Always-Valid p (Spend)", "Always-valid p")], "Series": [C("Arms", "Email", "Email")]},
               "Always-valid p-value for spend, by day (call it below 0.05)",
               objects={"valueAxis": [{"properties": {"axisScale": lit("log")}}]}, sort=(C(SQ, "day"), "Ascending"), z=10),
        visual(p2, "naive", "lineChart", 644, 184, 612, 524,
               {"Category": [C(SQ, "day", "Day")], "Y": [M(SQ, "Usual p (Spend)", "Usual p")], "Series": [C("Arms", "Email", "Email")]},
               "The usual p-value for spend, by day (not safe to check daily)",
               objects={"valueAxis": [{"properties": {"axisScale": lit("log")}}]}, sort=(C(SQ, "day"), "Ascending"), z=11),
    ]),
    (p3, "Who it works for", [
        text_box(p3, "title", 24, 12, 860, 52, "Guardrail: no customer group may be clearly worse off", 18),
        slicer(p3, "group", 900, 8, 356, 64, C(SG, "Group by", "Group by"), None),
        card(p3, "harm", 24, 76, 600, 96, M(SG, "Groups Harmed", "Groups harmed")),
        card(p3, "small", 636, 76, 620, 96, M(SG, "Groups Too Small to Tell", "Groups too small to tell")),
        visual(p3, "bars", "clusteredBarChart", 24, 184, 600, 524,
               {"Category": [C(SG, "level", "Group")], "Y": [M(SG, "Segment Spend Change", "Spend change vs no email")], "Series": [C("Arms", "Email", "Email")]},
               "Change in spend per customer, by group", sort=(C(SG, "level"), "Ascending"), z=10),
        visual(p3, "table", "tableEx", 640, 184, 616, 524,
               {"Values": [C(SG, "Group by", "Group by"), C(SG, "level", "Group"), C("Arms", "Email", "Email"), C(SG, "n", "Customers"),
                           M(SG, "Segment Spend Change", "Change"), C(SG, "lo", "95% low"), C(SG, "hi", "95% high"), C(SG, "status", "Guardrail")]},
               "Every group, with its interval and guardrail status", objects={"total": [{"properties": {"totals": lit(False)}}]}, z=11),
    ]),
    (p4, "The decision", [
        text_box(p4, "title", 24, 12, 1232, 52, "Which email, to whom, and is it worth the send? Set your own margin and email cost", 18),
        slicer(p4, "margin", 24, 70, 300, 64, C("Margin", "Margin", "Gross margin"), "Gross margin (default 35%)", single=True),
        slicer(p4, "cost", 336, 70, 300, 64, C("Email Cost", "Email Cost", "Cost per email"), "Cost per email (default $0.02)", single=True),
        slicer(p4, "size", 648, 70, 300, 64, C("List Size", "List Size", "Customers"), "Customers on the list (default 100,000)", single=True),
        card(p4, "be", 960, 70, 296, 96, M(PO, "Break-Even Email Cost", "Targeting pays above this email cost")),
        card(p4, "best", 24, 146, 924, 80, M(PO, "Best Option", "Best option at these settings"), size=20),
        visual(p4, "profit", "clusteredBarChart", 24, 238, 600, 470,
               {"Category": [C(PO, "policy", "Option")], "Y": [M(PO, "Extra Profit", "Extra profit vs sending nothing")]},
               "Extra profit against sending nothing", objects={"dataPoint": [{"properties": {"fill": color(TEAL)}}],
                                                                "labels": [{"properties": {"show": lit(True)}}]},
               sort=(M(PO, "Extra Profit"), "Descending"), z=10),
        visual(p4, "table", "tableEx", 640, 238, 616, 470,
               {"Values": [C(PO, "policy", "Option"), C(PO, "share_emailed", "Emailed"), C(PO, "lift_vs_nobody", "Extra spend per customer"),
                           C(PO, "lo", "95% low"), C(PO, "hi", "95% high"), M(PO, "Extra Profit", "Extra profit")]},
               "Options scored on the held-out half of customers", sort=(M(PO, "Extra Profit"), "Descending"),
               objects={"total": [{"properties": {"totals": lit(False)}}]}, z=11),
    ]),
]

SPEC = dict(name=NAME, root=ROOT, tables=TABLES, measures=MEASURES, relationships=RELATIONSHIPS, pages=PAGES,
            base_url="https://raw.githubusercontent.com/QaisBello/email-experiment/main/data/cleaned/",
            base_desc="Folder of cleaned CSVs from this repo (data/cleaned). Point it at a local folder or another branch to test.")

if __name__ == "__main__":
    build(SPEC)
    print("sort checks:", check_sorts(SPEC, os.path.join(os.path.dirname(ROOT), "data", "cleaned")) or "ok")
