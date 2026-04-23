-- Seasonal index: how much does each month deviate from the annual mean?
-- Business question: which months should ops plan for elevated demand?
-- An index of 1.18 in January means demand is 18% above average — that's the kind of
-- number that should feed directly into headcount planning conversations.
-- Nithin Arisetty, 2024

WITH monthly_averages AS (
    -- average demand for each calendar month across all years in the dataset
    SELECT
        CAST(strftime('%m', date) AS INTEGER)   AS month_num,
        CASE strftime('%m', date)
            WHEN '01' THEN 'January'
            WHEN '02' THEN 'February'
            WHEN '03' THEN 'March'
            WHEN '04' THEN 'April'
            WHEN '05' THEN 'May'
            WHEN '06' THEN 'June'
            WHEN '07' THEN 'July'
            WHEN '08' THEN 'August'
            WHEN '09' THEN 'September'
            WHEN '10' THEN 'October'
            WHEN '11' THEN 'November'
            WHEN '12' THEN 'December'
        END                                      AS month_name,
        AVG(demand_index)                        AS avg_demand_this_month
    FROM demand_signals
    WHERE demand_index IS NOT NULL
    GROUP BY 1
),

annual_mean AS (
    -- single number: the overall mean across all months, used as denominator
    -- separating this out because referencing it inline inside the ratio would
    -- require a correlated subquery, which gets messy fast
    SELECT AVG(demand_index) AS overall_avg
    FROM demand_signals
    WHERE demand_index IS NOT NULL
)

SELECT
    m.month_num,
    m.month_name,
    ROUND(m.avg_demand_this_month, 2)            AS avg_demand,
    ROUND(m.avg_demand_this_month / a.overall_avg, 3) AS seasonal_index
    -- index > 1.0 = above average demand; < 1.0 = below average
    -- ops should plan for elevated headcount in months where index > 1.10
FROM monthly_averages m
CROSS JOIN annual_mean a
ORDER BY m.month_num;
