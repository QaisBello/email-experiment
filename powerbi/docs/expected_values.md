# Expected values

From `tools/expected.py`, recomputed from the CSVs and checked against the Python analysis (`summary.json`): **all agree**.

## Page 1: The call

| Card | Expected |
|---|---:|
| Spend per customer, men's email vs none | +$0.77 |
| As a % of no-email spend | +118% |
| Men's vs women's email | +$0.35 |
| Safe to call on day (of 14) | 5 |
| Customer groups harmed | 0 |

| Email | Spend per customer | Visit rate | Purchase rate |
|---|---:|---:|---:|
| No email | $0.65 | 10.6% | 0.57% |
| Men's email | $1.42 | 18.3% | 1.25% |
| Women's email | $1.08 | 15.1% | 0.88% |

## Page 2: When to stop

| Card | Expected |
|---|---:|
| Fake tests 'won', usual p checked daily | 18.6% |
| Fake tests 'won', always-valid p | 0.2% |

## Page 3: Who it works for

| Card | Expected |
|---|---:|
| Groups harmed | 0 |
| Groups too small to tell | 1 |

## Page 4: The decision (defaults: 35% margin, $0.02 per email, 100,000 customers)

| Option | Extra profit |
|---|---:|
| Men's email to all | $26,030 |
| Targeted (by cell) | $25,635 |
| Women's email to all | $14,565 |
| Email nobody | $0 |

Best option: **Men's email to all**. Targeting pays above an email cost of **$0.037**.
