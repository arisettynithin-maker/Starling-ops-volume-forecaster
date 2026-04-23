-- Forecast accuracy retrospective: compare held-out actuals vs forecast
-- Business question: how well did our demand forecasts hold up vs what actually happened?
-- This is a MAPE calculation — industry standard for forecasting accuracy.
-- For context, sub-10% MAPE is good for monthly operational forecasting;
-- 10-20% is acceptable; above 20% should trigger a model review.
-- Nithin Arisetty, 2024

-- NOTE: in a real setup, forecast_values would come from a separate forecast table
-- populated by the Prophet model output. Here I'm simulating it with a naive
-- 3-month lag (i.e., "forecast" = the value 3 months ago, as a baseline benchmark).
-- The Prophet model in the notebook should beat this comfortably.

WITH actuals AS (
    SELECT
        date,
        demand_index AS actual_demand
    FROM demand_signals
    WHERE demand_index IS NOT NULL
),

naive_forecast AS (
    -- naive forecast: value from 3 months ago
    -- this is the benchmark we want to beat with the real model
    SELECT
        date,
        demand_index                                        AS actual_demand,
        LAG(demand_index, 3) OVER (ORDER BY date)          AS naive_forecast_3m,
        LAG(demand_index, 1) OVER (ORDER BY date)          AS naive_forecast_1m  -- also 1-month naive
    FROM demand_signals
    WHERE demand_index IS NOT NULL
),

errors AS (
    SELECT
        date,
        actual_demand,
        ROUND(naive_forecast_3m, 2)                                                          AS forecast_3m,
        ROUND(naive_forecast_1m, 2)                                                          AS forecast_1m,
        ROUND(ABS(actual_demand - naive_forecast_3m), 3)                                     AS abs_error_3m,
        ROUND(ABS(actual_demand - naive_forecast_3m) / NULLIF(actual_demand, 0) * 100, 2)   AS pct_error_3m,
        ROUND(ABS(actual_demand - naive_forecast_1m) / NULLIF(actual_demand, 0) * 100, 2)   AS pct_error_1m
    FROM naive_forecast
    WHERE naive_forecast_3m IS NOT NULL
)

SELECT
    date,
    actual_demand,
    forecast_3m,
    abs_error_3m,
    pct_error_3m,
    pct_error_1m,
    -- rolling MAPE over last 6 months — gives a sense of whether accuracy is improving
    ROUND(
        AVG(pct_error_3m) OVER (ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
        2
    )                                                       AS rolling_6m_mape
FROM errors
ORDER BY date;
