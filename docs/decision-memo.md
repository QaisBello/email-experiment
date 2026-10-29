# Decision memo: spring email campaign (EXP-2008-03-EMAIL)

**Call:** Send the men's email to the whole list.

## What we tested

64,000 customers who bought in the last 12 months were split at random into three equal groups: a men's merchandise email, a women's merchandise email, and no email. We measured site visits, purchases and spend over the following two weeks.

## What happened

| Metric (per customer) | No email | Men's email | Women's email |
|---|---|---|---|
| Spend | $0.65 | $1.42 (+$0.77) | $1.08 (+$0.42) |
| Purchase rate | 0.57% | 1.25% | 0.88% |
| Site visit rate | 10.6% | 18.3% | 15.1% |

All six differences hold after adjusting for multiple comparisons. The men's email beat the women's email on spend by $0.35 per customer (95% interval $0.03 to $0.66, p = 0.03).

## Why the call is safe

1. **Fair split.** Group sizes match the design (p = 0.90) and the groups look alike on everything measured before the send.
2. **No group harmed.** No customer group is worse off with either email. The $1,000+ spenders (2% of the list) are too few to judge, but their estimates are positive.
3. **Not a lucky peek.** With always-valid p-values the result was callable from day 5 of 14. The usual p-value, checked daily, raises false alarms in 19% of no-difference tests; ours did in 0.2%.

## Options considered

| Option | Extra spend per customer vs nothing | Share emailed |
|---|---|---|
| Men's email to all | +$0.80 | 100% |
| Targeted by customer type | +$0.78 | 77% |
| Women's email to all | +$0.47 | 100% |

These were scored on a held-out half of customers. Targeting skips returning men's-only buyers, and sends the women's email to new women's-only buyers. At a 35% margin it beats emailing everyone only when an email costs more than about $0.04, and the gap is well inside the noise. Simple wins.

## Risks and what we don't know

- The effect is measured over two weeks. Unsubscribes, list fatigue and long-term value are not in the data.
- Margin and email cost are assumptions. The live readout lets you set your own.

## Next test

Record each customer's spend in the two weeks before the next send. Last year's spend barely predicts spend after an email (r = 0.02), so CUPED could not shorten this test. A same-metric pre-period gives it something to work with.

*Full readout: https://qaisbello.github.io/data-science/email-experiment/*
