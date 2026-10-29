"""Checks that the published numbers hold up. Run: pytest -q"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "data" / "cleaned"
S = json.load(open(C / "summary.json"))
D = pd.read_csv(C / "customers.csv")
CFG = yaml.safe_load(open(ROOT / "metrics.yml"))


def test_one_row_per_customer_and_arms():
    assert len(D) == 64000 and D.customer_id.is_unique
    assert set(D.arm) == {CFG["experiment"]["control"], *CFG["experiment"]["treatments"]}


def test_split_is_fair():
    assert S["srm"]["p"] > 0.001
    assert S["max_abs_smd"] < 0.05


def test_every_registry_metric_is_reported():
    est = pd.read_csv(C / "estimates.csv")
    for m in CFG["metrics"]:
        for t in CFG["experiment"]["treatments"]:
            assert ((est.metric == m["id"]) & (est.arm == t)).sum() == 1


def test_headline_recomputes_from_customers():
    ctrl = D.spend[D.arm == "No E-Mail"].mean()
    mens = D.spend[D.arm == "Mens E-Mail"].mean()
    assert abs((mens - ctrl) - S["estimates"]["spend|Mens E-Mail"]["diff"]) < 1e-9


def test_holm_adjusted_never_below_raw():
    est = pd.read_csv(C / "estimates.csv")
    assert (est.p_holm >= est.p - 1e-12).all()


def test_always_valid_keeps_its_promise():
    assert S["aa_test"]["always_valid_false_alarm"] <= CFG["alpha"]
    assert S["aa_test"]["naive_false_alarm"] > S["aa_test"]["always_valid_false_alarm"]


def test_always_valid_p_never_rises():
    q = pd.read_csv(C / "sequential.csv")
    for _, g in q.groupby(["metric", "arm"]):
        assert np.all(np.diff(g.sort_values("day").p_always_valid.values) <= 1e-12)


def test_no_group_harmed():
    assert S["harmed_segments"] == []


def test_policy_scored_on_holdout_has_baseline_zero():
    p = pd.read_csv(C / "policy.csv").set_index("policy")
    assert p.loc["Email nobody", "lift_vs_nobody"] == 0
    assert 0 < p.loc["Targeted (by cell)", "share_emailed"] < 1
