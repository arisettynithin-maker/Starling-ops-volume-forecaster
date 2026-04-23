-- Prepare a regression-ready dataset: demand index with macro indicators as columns
-- Business question: which macro factors best explain demand variation?
-- This output feeds directly into the Python regression / correlation analysis in the notebook.
-- The pivot approach here is just to get everything in one row per month —
-- easier to plug into scikit-learn or statsmodels than a tall format.
-- Nithin Arisetty, 2024

WITH base AS (
    SELECT
        d.date,
        d.demand_index,
        d.fca_complaints,
        d.trends_starling,
        -- lagged macro indicators — economic conditions affect complaints with a delay,
        -- typically 1-2 months before they show up in ops volumes
        m.unemployment_rate,
        LAG(m.unemployment_rate, 1) OVER (ORDER BY d.date) AS unemployment_lag1,
        LAG(m.unemployment_rate, 2) OVER (ORDER BY d.date) AS unemployment_lag2,
        m.consumer_confidence,
        LAG(m.consumer_confidence, 1) OVER (ORDER BY d.date) AS confidence_lag1,
        -- interaction term: high unemployment + low confidence = likely double pressure on ops
        m.unemployment_rate * ABS(NULLIF(m.consumer_confidence, 0)) AS macro_stress_index
    FROM demand_signals d
    LEFT JOIN macro_indicators m ON d.date = m.date
    WHERE d.demand_index IS NOT NULL
)

SELECT
    date,
    ROUND(demand_index, 3)          AS demand_index,          -- target variable
    ROUND(fca_complaints, 0)        AS fca_complaints,
    ROUND(trends_starling, 1)       AS trends_starling,
    unemployment_rate,
    unemployment_lag1,
    unemployment_lag2,
    consumer_confidence,
    confidence_lag1,
    ROUND(macro_stress_index, 3)    AS macro_stress_index
FROM base
WHERE unemployment_rate IS NOT NULL    -- drop the first couple of months where lags are null
  AND unemployment_lag2 IS NOT NULL
ORDER BY date;
