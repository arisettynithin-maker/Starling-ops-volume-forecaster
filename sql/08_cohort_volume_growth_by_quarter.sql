-- Quarter-on-quarter volume cohorts showing growth acceleration/deceleration
-- Business question: is demand growth speeding up or slowing down?
-- Acceleration matters more than the absolute level for medium-term headcount planning —
-- if QoQ growth is consistently 5%+, we need to be hiring ahead of demand.
-- Nithin Arisetty, 2024

WITH quarterly AS (
    -- collapse monthly demand to quarterly total
    SELECT
        strftime('%Y', date) || '-Q' ||
            CASE
                WHEN CAST(strftime('%m', date) AS INTEGER) BETWEEN 1 AND 3  THEN '1'
                WHEN CAST(strftime('%m', date) AS INTEGER) BETWEEN 4 AND 6  THEN '2'
                WHEN CAST(strftime('%m', date) AS INTEGER) BETWEEN 7 AND 9  THEN '3'
                ELSE '4'
            END                              AS quarter,
        -- keeping the MIN date for ordering — DATE_TRUNC equivalent in SQLite
        MIN(date)                            AS quarter_start,
        SUM(demand_index)                    AS quarterly_demand,
        COUNT(*)                             AS months_in_quarter   -- sanity check: should always be 3
    FROM demand_signals
    WHERE demand_index IS NOT NULL
    GROUP BY 1
),

with_growth AS (
    SELECT
        quarter,
        quarter_start,
        ROUND(quarterly_demand, 2)          AS quarterly_demand,
        months_in_quarter,
        LAG(quarterly_demand) OVER (ORDER BY quarter_start)  AS prev_quarter_demand,
        LEAD(quarterly_demand) OVER (ORDER BY quarter_start) AS next_quarter_demand
    FROM quarterly
)

SELECT
    quarter,
    quarterly_demand,
    prev_quarter_demand,
    ROUND(
        100.0 * (quarterly_demand - prev_quarter_demand) / NULLIF(prev_quarter_demand, 0),
        1
    )                                       AS qoq_growth_pct,
    -- acceleration = this quarter's growth vs prior quarter's growth
    -- positive means growth is accelerating, negative means it's slowing
    ROUND(
        (100.0 * (quarterly_demand - prev_quarter_demand) / NULLIF(prev_quarter_demand, 0))
        - (100.0 * (prev_quarter_demand - LAG(quarterly_demand, 2) OVER (ORDER BY quarter_start))
           / NULLIF(LAG(quarterly_demand, 2) OVER (ORDER BY quarter_start), 0)),
        1
    )                                       AS growth_acceleration_pp
FROM with_growth
WHERE prev_quarter_demand IS NOT NULL
ORDER BY quarter_start;
