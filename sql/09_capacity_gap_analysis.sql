-- Capacity gap analysis: if demand grows X%, what's the headcount delta?
-- Business question: how many additional FTEs does ops need under different growth scenarios?
-- This is a simplified model — real capacity planning would layer in AHT, shrinkage,
-- occupancy targets — but it gives a ballpark that's useful for budget conversations.
-- Nithin Arisetty, 2024

-- Parameters (adjust these CTEs to run different scenarios)
WITH params AS (
    SELECT
        0.10    AS demand_growth_rate,   -- 10% YoY demand increase scenario
        45      AS avg_handle_time_mins, -- average minutes per contact (assumption)
        160     AS fte_hours_per_month,  -- productive hours per FTE per month
        0.85    AS occupancy_target      -- target occupancy rate (85% is standard for banking ops)
),

current_baseline AS (
    -- take the last 3 months as current demand baseline to smooth out any recent spikes
    SELECT
        AVG(demand_index) AS current_demand_index,
        AVG(fca_complaints) AS current_monthly_contacts
    FROM demand_signals
    WHERE date >= (SELECT DATE(MAX(date), '-3 months') FROM demand_signals)
      AND demand_index IS NOT NULL
),

scenario AS (
    SELECT
        b.current_monthly_contacts,
        b.current_demand_index,
        p.demand_growth_rate,
        -- projected contacts = current * (1 + growth rate)
        b.current_monthly_contacts * (1 + p.demand_growth_rate)  AS projected_contacts,
        -- required FTE = (projected contacts * AHT in hours) / (FTE hours * occupancy)
        ROUND(
            (b.current_monthly_contacts * (1 + p.demand_growth_rate) * p.avg_handle_time_mins / 60.0)
            / (p.fte_hours_per_month * p.occupancy_target),
            1
        )                                                          AS required_fte_projected,
        ROUND(
            (b.current_monthly_contacts * p.avg_handle_time_mins / 60.0)
            / (p.fte_hours_per_month * p.occupancy_target),
            1
        )                                                          AS required_fte_current
    FROM current_baseline b
    CROSS JOIN params p
)

SELECT
    ROUND(current_monthly_contacts, 0)  AS current_monthly_contacts,
    ROUND(projected_contacts, 0)        AS projected_monthly_contacts,
    ROUND(100.0 * demand_growth_rate, 0) || '%' AS growth_scenario,
    required_fte_current,
    required_fte_projected,
    ROUND(required_fte_projected - required_fte_current, 1) AS headcount_gap
FROM scenario;
