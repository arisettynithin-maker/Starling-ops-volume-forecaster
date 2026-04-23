-- Flag months where demand is anomalously high (> 1.5x the rolling average)
-- Business question: when did ops face unexpected demand spikes, and were they predictable?
-- This feeds into incident retrospectives — if the spike was visible in search trends
-- before it hit complaints, future monitoring could catch it earlier.
-- Nithin Arisetty, 2024

WITH rolling_baseline AS (
    SELECT
        date,
        demand_index,
        -- 3-month rolling average as the baseline; using 3 not 4 here because
        -- monthly data gives fewer data points and I want to be responsive
        AVG(demand_index) OVER (
            ORDER BY date
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING   -- exclude current month from its own baseline
        ) AS rolling_avg_excl_current
    FROM demand_signals
    WHERE demand_index IS NOT NULL
),

flagged AS (
    SELECT
        date,
        ROUND(demand_index, 2)                  AS demand_index,
        ROUND(rolling_avg_excl_current, 2)       AS rolling_baseline,
        ROUND(demand_index / NULLIF(rolling_avg_excl_current, 0), 3) AS ratio_to_baseline,
        CASE
            WHEN demand_index > 1.5 * rolling_avg_excl_current THEN 'HIGH SPIKE'
            WHEN demand_index > 1.2 * rolling_avg_excl_current THEN 'elevated'
            WHEN demand_index < 0.8 * rolling_avg_excl_current THEN 'below normal'
            ELSE 'normal'
        END                                      AS anomaly_flag
    FROM rolling_baseline
    WHERE rolling_avg_excl_current IS NOT NULL   -- first few months have no baseline
)

SELECT *
FROM flagged
ORDER BY date;
