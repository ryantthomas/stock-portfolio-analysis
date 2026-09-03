{{ config(materialized='view') }}

{#
    One clean row per ticker per day. The API upserts on (ticker, price_date),
    but a provider switch mid-session can still leave two rows for the same
    day, so the most recently loaded one wins.
#}

with ranked as (

    select
        upper(trim(ticker))          as ticker,
        price_date,
        adj_close,
        provider,
        loaded_at,
        row_number() over (
            partition by upper(trim(ticker)), price_date
            order by loaded_at desc
        ) as recency_rank
    from {{ source('raw', 'prices') }}
    where adj_close is not null
      and adj_close > 0

)

select
    ticker,
    price_date,
    adj_close,
    provider,
    loaded_at
from ranked
where recency_rank = 1
