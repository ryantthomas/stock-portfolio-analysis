{{ config(materialized='view') }}

{#
    Portfolio snapshots with weights renormalized to sum to exactly 1 within
    each portfolio. Users enter percentages, decimals or raw ratios, so every
    downstream model can rely on weights being a proper distribution.
#}

with holdings as (

    select
        portfolio_id,
        label                as portfolio_label,
        upper(trim(ticker))  as ticker,
        weight               as raw_weight,
        upper(trim(coalesce(benchmark, 'SPY'))) as benchmark,
        created_at
    from {{ source('raw', 'portfolio_holdings') }}
    where weight > 0

),

totals as (

    select
        portfolio_id,
        sum(raw_weight) as total_weight
    from holdings
    group by 1

)

select
    h.portfolio_id,
    h.portfolio_label,
    h.ticker,
    h.raw_weight,
    h.raw_weight / t.total_weight as weight,
    h.benchmark,
    h.created_at
from holdings h
join totals t using (portfolio_id)
where t.total_weight > 0
