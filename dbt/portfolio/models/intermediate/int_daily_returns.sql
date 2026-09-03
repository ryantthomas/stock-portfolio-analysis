{{ config(materialized='view') }}

{#
    Daily simple returns per ticker. The lag is taken over each ticker's own
    price history rather than a shared calendar, so a symbol that does not
    trade on a given day simply has no row instead of a phantom 0% return.
#}

with sequenced as (

    select
        ticker,
        price_date,
        adj_close,
        lag(adj_close) over (partition by ticker order by price_date) as prev_close
    from {{ ref('stg_prices') }}

)

select
    ticker,
    price_date,
    adj_close,
    prev_close,
    adj_close / prev_close - 1 as daily_return
from sequenced
where prev_close is not null
  and prev_close > 0
