"""Email experiment readout: cleaning, validity checks, estimates, sequential monitoring,
segment effects and a targeting policy. Every number in the readout comes from here.

Run:  python src/analyse.py
Reads data/raw/hillstrom.csv and metrics.yml; writes data/cleaned/.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hillstrom.csv"
OUT = ROOT / "data" / "cleaned"
CFG = yaml.safe_load(open(ROOT / "metrics.yml", encoding="utf-8"))
SEED = 20080320
OUT.mkdir(parents=True, exist_ok=True)

CONTROL = CFG["experiment"]["control"]
TREATS = CFG["experiment"]["treatments"]
ARMS = [CONTROL] + TREATS
METRICS = CFG["metrics"]
ALPHA = CFG["alpha"]
log = []


def note(issue, rows, action):
    log.append({"check": issue, "rows_affected": int(rows), "action": action})


# ---------------------------------------------------------------- 1. clean
def clean():
    d = pd.read_csv(RAW)
    note("Rows loaded", len(d), "64,000 customers, one row each, 3 arms")
    note("Missing values", int(d.isna().sum().sum()), "None found")
    dup = int(d.duplicated().sum())
    note("Identical rows", dup,
         "Kept. There is no customer ID and every column is coarse (bands, flags, mostly-zero outcomes), "
         "so identical rows are expected for different customers")
    bad = int(((d.spend > 0) & (d.conversion == 0)).sum() + ((d.conversion == 1) & (d.spend == 0)).sum()
              + ((d.conversion == 1) & (d.visit == 0)).sum())
    note("Purchase without spend, spend without purchase, or purchase without visit", bad, "None found")
    bins = [0, 100, 200, 350, 500, 750, 1000, np.inf]
    band = pd.cut(d.history, bins, right=False, labels=range(1, 8)).astype(int)
    mism = int((band != d.history_segment.str[:1].astype(int)).sum())
    note("History band disagrees with history dollars", mism, "None found")
    neither = int(((d.mens == 0) & (d.womens == 0)).sum())
    note("Customer bought neither men's nor women's items last year", neither, "None found")
    typo = int((d.zip_code == "Surburban").sum())
    d["zip_code"] = d.zip_code.replace({"Surburban": "Suburban"})
    note('Area spelled "Surburban"', typo, 'Renamed to "Suburban"')

    d.insert(0, "customer_id", [f"C{i:05d}" for i in range(1, len(d) + 1)])
    d["arm"] = d.segment
    d["purchase_history"] = np.select([(d.mens == 1) & (d.womens == 1), d.mens == 1], ["Both", "Men's only"], "Women's only")
    d["history_band"] = d.history_segment.str.replace(r"^\d\) ", "", regex=True)
    d["recency_band"] = pd.cut(d.recency, [0, 3, 6, 9, 12], labels=["1-3 months", "4-6 months", "7-9 months", "10-12 months"]).astype(str)
    d["newbie"] = np.where(d.newbie == 1, "New this year", "Returning")
    cols = ["customer_id", "arm", "recency", "recency_band", "history", "history_band", "purchase_history",
            "newbie", "channel", "zip_code", "visit", "conversion", "spend"]
    d = d[cols]
    d.to_csv(OUT / "customers.csv", index=False)
    return d


# ---------------------------------------------------------------- helpers
def diff_ci(y_t, y_c):
    """Welch difference in means with a 95% interval."""
    m_t, m_c = y_t.mean(), y_c.mean()
    se = np.sqrt(y_t.var(ddof=1) / len(y_t) + y_c.var(ddof=1) / len(y_c))
    z = stats.norm.ppf(1 - ALPHA / 2)
    diff = m_t - m_c
    p = 2 * stats.norm.sf(abs(diff / se)) if se > 0 else 1.0
    return dict(treat=m_t, control=m_c, diff=diff, se=se, lo=diff - z * se, hi=diff + z * se, p=p,
                rel=diff / m_c if m_c else np.nan)


def holm(pvals):
    order = np.argsort(pvals)
    m = len(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# ---------------------------------------------------------------- 2. validity
def validity(d):
    n = d.arm.value_counts().reindex(ARMS)
    chi, p = stats.chisquare(n.values)
    srm = dict(counts={a: int(n[a]) for a in ARMS}, chi2=float(chi), p=float(p), ok=bool(p > 0.001))
    rows = []
    covs = {"history": d.history, "recency": d.recency,
            "new this year": (d.newbie == "New this year").astype(float),
            "bought men's": d.purchase_history.isin(["Men's only", "Both"]).astype(float),
            "bought women's": d.purchase_history.isin(["Women's only", "Both"]).astype(float),
            "web channel": (d.channel == "Web").astype(float),
            "urban": (d.zip_code == "Urban").astype(float)}
    for name, x in covs.items():
        for t in TREATS:
            a, b = x[d.arm == t], x[d.arm == CONTROL]
            smd = (a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2)
            rows.append(dict(covariate=name, arm=t, smd=float(smd)))
    bal = pd.DataFrame(rows)
    bal.to_csv(OUT / "balance.csv", index=False)
    return srm, float(bal.smd.abs().max())


# ---------------------------------------------------------------- 3. estimates
def estimates(d):
    rows = []
    x = d.history.values
    for m in METRICS:
        y = d[m["column"]].astype(float).values
        # CUPED: theta from the pooled data, adjusted outcome y - theta (x - mean x)
        theta = np.cov(y, x)[0, 1] / np.var(x, ddof=1)
        y_cuped = y - theta * (x - x.mean())
        for t in TREATS:
            it, ic = (d.arm == t).values, (d.arm == CONTROL).values
            raw = diff_ci(pd.Series(y[it]), pd.Series(y[ic]))
            cup = diff_ci(pd.Series(y_cuped[it]), pd.Series(y_cuped[ic]))
            rows.append(dict(metric=m["id"], metric_name=m["name"], role=m["role"], arm=t,
                             control_mean=raw["control"], treat_mean=raw["treat"], diff=raw["diff"],
                             rel=raw["rel"], lo=raw["lo"], hi=raw["hi"], p=raw["p"],
                             cuped_diff=cup["diff"], cuped_lo=cup["lo"], cuped_hi=cup["hi"],
                             variance_reduction=1 - (cup["se"] / raw["se"]) ** 2))
    e = pd.DataFrame(rows)
    e["p_holm"] = holm(e.p.values)
    e["significant"] = e.p_holm < ALPHA
    # bootstrap check for the heavy-tailed spend metric
    rng = np.random.default_rng(SEED)
    boots = {}
    for t in TREATS:
        yt = d.spend[d.arm == t].values
        yc = d.spend[d.arm == CONTROL].values
        bs = [rng.choice(yt, len(yt)).mean() - rng.choice(yc, len(yc)).mean() for _ in range(2000)]
        boots[t] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    e.to_csv(OUT / "estimates.csv", index=False)
    return e, boots


# ---------------------------------------------------------------- 4. sequential monitoring
def msprt_p(diffs, variances, tau2):
    """Always-valid p-values for a normal mixture SPRT (Johari et al.)."""
    p, out = 1.0, []
    for th, v in zip(diffs, variances):
        lam = np.sqrt(v / (v + tau2)) * np.exp(tau2 * th ** 2 / (2 * v * (v + tau2)))
        p = min(p, 1 / lam)
        out.append(p)
    return out


def sequential(d, days=14):
    """The data has no timestamps. Customers are put in a seeded random arrival order and
    released in 14 equal daily batches, to show how the readout would look if checked daily."""
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(d))
    day = np.empty(len(d), int)
    day[order] = np.arange(len(d)) * days // len(d) + 1
    d = d.assign(day=day)
    mde = {"spend": 0.25, "conversion": 0.003, "visit": 0.02}
    rows = []
    for m in METRICS:
        col = m["column"]
        for t in TREATS:
            diffs, vars_, naive = [], [], []
            for k in range(1, days + 1):
                s = d[d.day <= k]
                r = diff_ci(s[col][s.arm == t].astype(float), s[col][s.arm == CONTROL].astype(float))
                diffs.append(r["diff"]); vars_.append(r["se"] ** 2); naive.append(r["p"])
                rows.append(dict(metric=m["id"], arm=t, day=k, n=int(len(s)), diff=r["diff"], lo=r["lo"], hi=r["hi"], p_naive=r["p"]))
            av = msprt_p(diffs, vars_, mde[m["id"]] ** 2)
            for i, k in enumerate(range(1, days + 1)):
                rows[-days + i]["p_always_valid"] = av[i]
    seq = pd.DataFrame(rows)
    seq.to_csv(OUT / "sequential.csv", index=False)

    # A/A test: split the no-email group in two at random, peek daily, count false alarms
    ctrl = d[d.arm == CONTROL].reset_index(drop=True)
    y = ctrl.spend.values
    sims, naive_hits, av_hits = 1000, 0, 0
    for _ in range(sims):
        g = rng.integers(0, 2, len(ctrl)).astype(bool)
        dd = rng.permutation(len(ctrl)) * days // len(ctrl) + 1
        diffs, vars_, hit = [], [], False
        for k in range(1, days + 1):
            sel = dd <= k
            a, b = y[sel & g], y[sel & ~g]
            se2 = a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)
            df = a.mean() - b.mean()
            diffs.append(df); vars_.append(se2)
            if 2 * stats.norm.sf(abs(df) / np.sqrt(se2)) < ALPHA:
                hit = True
        naive_hits += hit
        av_hits += min(msprt_p(diffs, vars_, mde["spend"] ** 2)) < ALPHA
    aa = dict(simulations=sims, days=days, naive_false_alarm=naive_hits / sims, always_valid_false_alarm=av_hits / sims)
    pd.DataFrame([aa]).to_csv(OUT / "aa_test.csv", index=False)
    return seq, aa


# ---------------------------------------------------------------- 5. segments
def segments(d):
    rows = []
    for seg in CFG["segments"]:
        for level, g in d.groupby(seg):
            for t in TREATS:
                r = diff_ci(g.spend[g.arm == t], g.spend[g.arm == CONTROL])
                rows.append(dict(segment=seg, level=level, arm=t, n=int(len(g)), share=len(g) / len(d),
                                 diff=r["diff"], lo=r["lo"], hi=r["hi"]))
    s = pd.DataFrame(rows)
    thr = CFG["guardrails"][0]["threshold"]
    # harmed: the whole interval is below zero. uncertain: too few customers to rule out a loss beyond the threshold
    s["status"] = np.where(s.hi < 0, "harmed", np.where(s.lo < thr, "too small to tell", "ok"))
    # one global sort key per level (levels are unique across segments), for charts and Power BI sort-by
    order = {"purchase_history": ["Men's only", "Women's only", "Both"],
             "history_band": ["$0 - $100", "$100 - $200", "$200 - $350", "$350 - $500", "$500 - $750", "$750 - $1,000", "$1,000 +"],
             "recency_band": ["1-3 months", "4-6 months", "7-9 months", "10-12 months"],
             "newbie": ["New this year", "Returning"], "channel": ["Web", "Phone", "Multichannel"], "zip_code": ["Urban", "Suburban", "Rural"]}
    keys = {lv: i for i, lv in enumerate(lv for sg in CFG["segments"] for lv in order[sg])}
    assert set(s.level) <= set(keys), set(s.level) - set(keys)
    s["level_order"] = s.level.map(keys)
    s.to_csv(OUT / "segments.csv", index=False)
    return s


# ---------------------------------------------------------------- 6. targeting policy
def policy(d):
    """Choose an email per cell on one random half, score every policy on the other half."""
    rng = np.random.default_rng(SEED + 1)
    d = d.assign(cell=d.purchase_history + " · " + d.newbie)
    train = rng.random(len(d)) < 0.5
    tr, te = d[train], d[~train]
    means = tr.groupby(["cell", "arm"]).spend.mean().unstack()
    best = means.idxmax(axis=1).to_dict()
    pols = {"Email nobody": lambda c: CONTROL, "Men's email to all": lambda c: TREATS[0],
            "Women's email to all": lambda c: TREATS[1], "Targeted (by cell)": lambda c: best[c]}

    def value(df, f):
        # randomised 1/3 each: the customers whose arm matches the policy are an unbiased sample
        chosen = df.cell.map(f) if f is not None else None
        match = df[df.arm == chosen]
        return match.spend.mean(), (chosen != CONTROL).mean()

    out = []
    base, _ = value(te, pols["Email nobody"])
    y = te.spend.values
    nob = (te.arm == CONTROL).values
    idx = rng.integers(0, len(te), (1000, len(te)))
    for name, f in pols.items():
        v, sent = value(te, f)
        match = (te.arm == te.cell.map(f)).values
        bs = [y[i][match[i]].mean() - y[i][nob[i]].mean() for i in idx]
        out.append(dict(policy=name, spend_per_customer=v, lift_vs_nobody=v - base,
                        lo=float(np.percentile(bs, 2.5)), hi=float(np.percentile(bs, 97.5)), share_emailed=sent))
    p = pd.DataFrame(out)
    p.to_csv(OUT / "policy.csv", index=False)
    cells = means.reset_index().melt(id_vars="cell", var_name="arm", value_name="train_spend")
    cells["chosen"] = cells.apply(lambda r: int(best[r.cell] == r.arm), axis=1)
    cells["customers"] = cells.cell.map(d.cell.value_counts())
    cells.to_csv(OUT / "policy_cells.csv", index=False)
    return p, best


def head_to_head(d):
    """The decision is which email, so compare the two emails directly."""
    out = {}
    for m in METRICS:
        r = diff_ci(d[m["column"]][d.arm == TREATS[0]].astype(float), d[m["column"]][d.arm == TREATS[1]].astype(float))
        out[m["id"]] = {k: float(v) for k, v in r.items()}
    return out


def reg_adjust(d):
    """CUPED uses one pre-period covariate. Regression adjustment uses every pre-treatment column.
    Returns the share of variance removed for each metric."""
    import statsmodels.formula.api as smf
    out = {}
    for m in METRICS:
        y = m["column"]
        f0 = smf.ols(f"{y} ~ C(arm)", d).fit(cov_type="HC1")
        f1 = smf.ols(f"{y} ~ C(arm) + history + recency + C(purchase_history) + C(newbie) + C(channel) + C(zip_code)", d).fit(cov_type="HC1")
        k = [c for c in f0.bse.index if c.startswith("C(arm)")][0]
        out[m["id"]] = float(1 - (f1.bse[k] / f0.bse[k]) ** 2)
    out["history_spend_correlation"] = float(np.corrcoef(d.history, d.spend)[0, 1])
    return out


def main():
    d = clean()
    srm, max_smd = validity(d)
    note("Sample ratio across the 3 arms", sum(srm["counts"].values()), f"chi-square p = {srm['p']:.2f}; split is as designed")
    est, boots = estimates(d)
    seq, aa = sequential(d)
    seg = segments(d)
    pol, best = policy(d)
    pd.DataFrame(log).to_csv(OUT / "data_quality_log.csv", index=False)

    def pick(metric, arm):
        r = est[(est.metric == metric) & (est.arm == arm)].iloc[0]
        return {k: (float(v) if isinstance(v, (float, np.floating)) else (bool(v) if isinstance(v, (bool, np.bool_)) else v)) for k, v in r.items()}

    first_call = {}
    for t in TREATS:
        s = seq[(seq.metric == "spend") & (seq.arm == t) & (seq.p_always_valid < ALPHA)]
        first_call[t] = int(s.day.min()) if len(s) else None
    summary = dict(
        experiment=CFG["experiment"], registry=CFG, customers=int(len(d)),
        arms={a: int((d.arm == a).sum()) for a in ARMS}, buyers=int(d.conversion.sum()),
        srm=srm, max_abs_smd=max_smd,
        estimates={f"{m['id']}|{t}": pick(m["id"], t) for m in METRICS for t in TREATS},
        bootstrap_spend_ci=boots,
        aa_test=aa, first_always_valid_call_day=first_call,
        harmed_segments=seg[seg.status == "harmed"][["segment", "level", "arm"]].to_dict("records"),
        uncertain_segments=seg[seg.status == "too small to tell"][["segment", "level", "arm", "n", "diff", "lo", "hi"]].to_dict("records"),
        head_to_head=head_to_head(d), regression_adjustment=reg_adjust(d),
        policy=pol.to_dict("records"), policy_choice=best,
    )
    json.dump(summary, open(OUT / "summary.json", "w"), indent=2, default=float)
    print(json.dumps({k: summary[k] for k in ["arms", "srm", "max_abs_smd", "aa_test", "first_always_valid_call_day", "harmed_segments", "policy_choice"]}, indent=1, default=float))
    print(est[["metric", "arm", "diff", "lo", "hi", "rel", "p_holm", "variance_reduction"]].round(4).to_string())
    print(pol.round(3).to_string())


if __name__ == "__main__":
    main()
