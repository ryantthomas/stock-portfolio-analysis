{{ config(materialized='view') }}

{#
    Daily return of each saved portfolio, assuming it is rebalanced back to
    target weights every day. That assumption is what makes the statistics
    describe the allocation the user entered rather than whatever it drifted
    into over the window.

    Days where not every holding traded are excluded, so a partial day never
    reads as a sudden portfolio-wide move.
#}

with holdings as (

    select * from {{ ref('stg_portfolio_holdings') }}

),

position_returns as (

    select
        h.portfolio_id,
        h.portfolio_label,
        h.benchmark,
        r.price_date,
        h.ticker,
        h.weight,
        r.daily_return,
        h.weight * r.daily_return as weighted_return
    from holdings h
    join {{ ref('int_daily_returns') }} r
      on r.ticker = h.ticker

),

expected_positions as (

    select portfolio_id, count(*) as position_count
    from holdings
    group by 1

)

select
    p.portfolio_id,
    p.portfolio_label,
    p.benchmark,
    p.price_date,
    sum(p.weighted_return) as portfolio_return,
    count(*)               as positions_priced,
    sum(p.weight)          as weight_covered
from position_returns p
join expected_positions e using (portfolio_id)
group by 1, 2, 3, 4, e.position_count
having count(*) = e.position_count
