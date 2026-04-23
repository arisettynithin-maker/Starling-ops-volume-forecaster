-- Year-over-year complaint volume growth by firm type
-- Business question: is our neobank segment growing complaints faster than the market?
-- If yes, that's an ops resourcing signal — not necessarily a quality signal.
-- Nithin Arisetty, 2024

WITH monthly_complaints AS (
    -- aggregate to year + firm_type grain first
    -- doing this in a CTE so the YoY calc below is cleaner to read
    SELECT
        strftime('%Y', date)   AS year,
        firm_type,
        SUM(complaints_received) AS total_complaints
    FROM complaints
    GROUP BY 1, 2
),

yoy AS (
    SELECT
        year,
        firm_type,
        total_complaints,
        LAG(total_complaints) OVER (
            PARTITION BY firm_type
            ORDER BY year
        ) AS prev_year_complaints
    FROM monthly_complaints
)

SELECT
    year,
    firm_type,
    total_complaints,
    prev_year_complaints,
    -- keeping the ROUND to 1dp; 2dp false precision for what's essentially a proxy metric
    ROUND(
        100.0 * (total_complaints - prev_year_complaints) / NULLIF(prev_year_complaints, 0),
        1
    ) AS yoy_pct_change
FROM yoy
WHERE prev_year_complaints IS NOT NULL
ORDER BY firm_type, year;
