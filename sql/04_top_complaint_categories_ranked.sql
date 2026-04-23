-- Top complaint categories ranked within each half-year period
-- Business question: which complaint types are driving volume in each period?
-- Useful for routing decisions — if "Cards & payments" is dominating, the ops team
-- needs more specialist agents on that queue, not just more headcount generally.
-- Nithin Arisetty, 2024

WITH period_category_volumes AS (
    SELECT
        -- grouping to half-year to match how FCA actually publishes this data
        CASE
            WHEN CAST(strftime('%m', date) AS INTEGER) <= 6
                THEN strftime('%Y', date) || ' H1'
            ELSE strftime('%Y', date) || ' H2'
        END                         AS period,
        category,
        SUM(complaints_received)    AS total_volume
    FROM complaints
    WHERE firm_type = 'neobank'   -- scoping to neobank segment; high-street would dilute this
      AND category IS NOT NULL
    GROUP BY 1, 2
)

SELECT
    period,
    category,
    total_volume,
    DENSE_RANK() OVER (
        PARTITION BY period
        ORDER BY total_volume DESC
    )                               AS rank_in_period,
    -- share of total complaints in that period — useful for proportion analysis
    ROUND(
        100.0 * total_volume / SUM(total_volume) OVER (PARTITION BY period),
        1
    )                               AS pct_of_period_total
FROM period_category_volumes
ORDER BY period, rank_in_period;
