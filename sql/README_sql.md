# SQL Query Reference

All queries run against the SQLite schema defined in `schema.sql`. The denormalised `demand_signals` table is what most queries hit — it mirrors `data/processed/combined_demand_signals.csv` exactly.

To run any of these locally:

```bash
sqlite3 starling_ops.db < sql/schema.sql
# then load data via the notebook (see notebooks/starling_volume_analysis.ipynb, section 2)
sqlite3 starling_ops.db < sql/01_complaint_volume_trend_yoy.sql
```

---

| File | Business Question | SQL Concepts |
|---|---|---|
| `schema.sql` | DDL for all tables | CREATE TABLE, indexes |
| `01_complaint_volume_trend_yoy.sql` | Is neobank complaint growth outpacing the market YoY? | `DATE()`, `LAG()`, YoY % change |
| `02_rolling_4week_avg_volume.sql` | What's the smoothed demand trend, stripping out noise? | `AVG() OVER (ROWS BETWEEN ...)` window function |
| `03_seasonal_index_by_month.sql` | Which months are structurally high demand vs annual mean? | CTE + aggregation + ratio indexing |
| `04_top_complaint_categories_ranked.sql` | Which complaint types dominate volume each period? | `DENSE_RANK() OVER (PARTITION BY ...)` |
| `05_search_vs_complaints_correlation.sql` | Does search volume lead complaints by 1–2 months? | Multi-table join, `LAG()` time alignment |
| `06_volume_spike_detection.sql` | When did demand spike beyond expected range? | CTE + `CASE WHEN` anomaly flagging |
| `07_macro_driver_regression_prep.sql` | Which macro factors explain demand variation? | `CASE WHEN` pivot, multi-join, lagged columns |
| `08_cohort_volume_growth_by_quarter.sql` | Is demand growth accelerating or slowing down? | Cohort logic, `LEAD()`, growth acceleration |
| `09_capacity_gap_analysis.sql` | Under a 10% growth scenario, what's the headcount gap? | Parameterised CTE, FTE arithmetic |
| `10_forecast_accuracy_retrospective.sql` | How accurate were our demand forecasts last quarter? | Self-join equivalent, `ABS()` error, MAPE |

---

A few notes on style:

- Comments explain *why*, not what. If the reason for a step isn't obvious from the code, there's a comment on it.
- CTEs are used whenever a subquery would need to be referenced more than once, or when it makes the logic easier to follow.
- `NULLIF(x, 0)` instead of bare division everywhere — SQLite silently returns NULL rather than crashing on divide-by-zero, but it's worth being explicit.
- The two "test firm" entries in the raw complaints data (flagged as `firm_type = 'test'`) are excluded across all queries using `WHERE firm_type = 'neobank'` or `firm_type = 'high_street'`.

*Nithin Arisetty, 2024*
