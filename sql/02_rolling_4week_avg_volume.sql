-- Rolling 4-week average demand index as a smoothed signal
-- Business question: what's the underlying trend once we strip out weekly noise?
-- The raw demand_index has some spikes that make it hard to communicate to stakeholders
-- — the 4-week rolling avg is what I'd actually put in a planning deck.
-- Nithin Arisetty, 2024

SELECT
    date,
    ROUND(demand_index, 2)                          AS raw_demand_index,
    ROUND(
        AVG(demand_index) OVER (
            ORDER BY date
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
        2
    )                                               AS rolling_4week_avg,
    -- deviation from the rolling avg — useful for spotting if we're trending up or down
    ROUND(
        demand_index - AVG(demand_index) OVER (
            ORDER BY date
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ),
        2
    )                                               AS deviation_from_avg
FROM demand_signals
WHERE demand_index IS NOT NULL
ORDER BY date;
