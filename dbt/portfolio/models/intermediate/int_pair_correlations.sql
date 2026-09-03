{{ config(materialized='view') }}

{#
    Pairwise return correlation for every ticker pair held in the same
    portfolio. The self-join is restricted to a < b so each pair appears once,
    and both legs are joined on price_date so correlation is only ever
    computed over days both securities actually traded.

    This is the number that decides whether a portfolio is genuinely
    diversified or just holds many tickers that do the same thing.
#}

with portfolio_pairs as (

    select distinct
        h1.portfolio_id,
        h1.ticker as ticker_a,
        h2.ticker as ticker_b
    from {{ ref('stg_portfolio_holdings') }} h1
    join {{ ref('stg_portfolio_holdings') }} h2
      on h1.portfolio_id = h2.portfolio_id
     and h1.ticker < h2.ticker

),

paired_returns as (

    select
        p.portfolio_id,
        p.ticker_a,
        p.ticker_b,
        ra.daily_return as return_a,
        rb.daily_return as return_b
    from portfolio_pairs p
    join {{ ref('int_daily_returns') }} ra on ra.ticker = p.ticker_a
    join {{ ref('int_daily_returns') }} rb
      on rb.ticker = p.ticker_b
     and rb.price_date = ra.price_date

)

select
    portfolio_id,
    ticker_a,
    ticker_b,
    count(*)                        as overlapping_days,
    corr(return_a, return_b)        as correlation,
    covar_samp(return_a, return_b)  as covariance
from paired_returns
group by 1, 2, 3
having count(*) >= {{ var('min_observations') }}
