{{ config(materialized='table') }}

{#
    The daily equity curve for each saved portfolio: growth of 100 invested at
    the start of the window, plus the drawdown path from the running peak.
#}

with returns as (

    select * from {{ ref('int_portfolio_daily_returns') }}

),

indexed as (

    select
        portfolio_id,
        portfolio_label,
        benchmark,
        price_date,
        portfolio_return,
        100 * exp(sum(ln(greatest(1 + portfolio_return, 0.000001)))
            over (partition by portfolio_id order by price_date)) as growth_index,
        row_number() over (partition by portfolio_id order by price_date) as trading_day
    from returns

)

select
    portfolio_id,
    portfolio_label,
    benchmark,
    price_date,
    trading_day,
    portfolio_return,
    growth_index,
    max(growth_index) over (
        partition by portfolio_id
        order by price_date
        rows between unbounded preceding and current row
    ) as peak_index,
    growth_index / max(growth_index) over (
        partition by portfolio_id
        order by price_date
        rows between unbounded preceding and current row
    ) - 1 as drawdown
from indexed
