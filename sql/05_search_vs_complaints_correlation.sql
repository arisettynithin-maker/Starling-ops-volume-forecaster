-- Lead/lag relationship between search volume and complaint volume
-- Business question: does search interest in "Starling Bank" predict complaints 1-2 months later?
-- If search is a leading indicator, we could use it in near-term forecasts before
-- the actual complaint data arrives (which has a publication lag of ~6 months).
-- Nithin Arisetty, 2024

WITH complaint_monthly AS (
    -- collapse complaints to monthly level for the join
    SELECT
        strftime('%Y-%m', date) AS ym,
        date,
        SUM(complaints_received) AS total_complaints
    FROM complaints
    WHERE firm_type = 'neobank'
    GROUP BY 1, 2
),

aligned AS (
    SELECT
        s.date,
        strftime('%Y-%m', s.date)   AS ym,
        s.trends_starling,
        s.trends_neobank_help,
        c.total_complaints,
        -- lag search by 1 month — checking if last month's search predicts this month's complaints
        LAG(s.trends_starling, 1) OVER (ORDER BY s.date) AS search_lag1,
        LAG(s.trends_starling, 2) OVER (ORDER BY s.date) AS search_lag2
    FROM search_trends s
    LEFT JOIN complaint_monthly c
           ON strftime('%Y-%m', s.date) = c.ym
    WHERE s.trends_starling IS NOT NULL
)

SELECT
    date,
    trends_starling         AS search_this_month,
    search_lag1             AS search_1m_ago,
    search_lag2             AS search_2m_ago,
    total_complaints        AS complaints_this_month
    -- in a real analysis I'd compute Pearson correlation here, but SQLite doesn't have
    -- a built-in CORR() — using this as input to the Python notebook instead
FROM aligned
WHERE total_complaints IS NOT NULL
ORDER BY date;
