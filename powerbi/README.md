# Send the men's email: Power BI

The email experiment readout as a Power BI report: the call, when it was safe to stop, who it works for, and a profit calculator with your own margin and email cost.

This folder is a Power BI project (`Email_Experiment.pbip`): a TMDL semantic model and a PBIR report. It is generated from one Python spec, checked against Microsoft's JSON schemas, and its numbers are recomputed independently in pandas.

## Open it

1. Open **`Email_Experiment.pbip`** in Power BI Desktop. In versions before mid-2025, first turn on the preview features for Power BI Project (.pbip), the TMDL model format and the PBIR report format.
2. Click **Refresh**. The model reads this repo's cleaned CSVs from GitHub through the **BaseUrl** parameter. If asked, choose **Anonymous** access for `raw.githubusercontent.com`.
3. Check the visuals against [`docs/expected_values.md`](docs/expected_values.md).

## Pages

- **The call:** five cards (men's email spend lift, as a %, men's vs women's, safe-to-call day, groups harmed); spend, visit and purchase rates by email; the Holm-adjusted scorecard.
- **When to stop:** false alarms from checking daily (usual vs always-valid p-value, from 1,000 fake tests); both p-values for spend by day on a log scale.
- **Who it works for:** change in spend for every customer group and email, with the guardrail status; a Group by slicer.
- **The decision:** margin, email cost and list size slicers (what-if tables); extra profit for each sending option; the best option and the email cost above which targeting pays.

## Model

- **Tables:** Customers (64,000 rows), Arms, Estimates, Sequential, Segments, Policy, AA Test, and three what-if tables (Margin, Email Cost, List Size) built in Power Query.
- **Relationships:** Customers, Estimates, Sequential and Segments each link to Arms on `arm`.
- **24 DAX measures** in display folders (Outcomes, Lift, Monitoring, Guardrail, What-if, Decision). The full DAX is in [`docs/measures.md`](docs/measures.md).

## Notes

- Spend, purchase and visit rates and every lift are computed in DAX from the customer rows.
- Holm-adjusted p-values, always-valid p-values, the A/A simulation, segment intervals and the holdout-scored options need more than aggregation, so they come from `src/analyse.py` and are loaded as tables.
- With nothing selected, the what-if slicers default to 35% margin, $0.02 per email and 100,000 customers, the same as the web readout.

## Rebuild and check

```bash
pip install jsonschema referencing pandas
python tools/spec.py        # the spec: writes the .pbip and its folders
python tools/validate.py    # Microsoft schemas, field and DAX references, name clashes
python tools/expected.py    # what the report should show, checked against the project's own results
```

`tools/pbikit.py` is the small shared library used across the portfolio for writing Power BI projects as code.
