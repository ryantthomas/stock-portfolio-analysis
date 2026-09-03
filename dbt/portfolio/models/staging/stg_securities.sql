{{ config(materialized='view') }}

{#
    Metadata with the provider's blanks and nulls collapsed into a single
    'Unknown' label, so downstream grouping does not fragment into
    null / '' / 'Unknown' buckets for what is really one category.
#}

with ranked as (

    select
        *,
        row_number() over (
            partition by upper(trim(ticker)) order by loaded_at desc
        ) as recency_rank
    from {{ source('raw', 'securities') }}

),

cleaned as (

    select
        upper(trim(ticker))                              as ticker,
        nullif(trim(coalesce(name, '')), '')             as security_name,
        coalesce(nullif(trim(sector), ''), 'Unknown')    as sector,
        coalesce(nullif(trim(industry), ''), 'Unknown')  as industry,
        coalesce(nullif(trim(country), ''), 'Unknown')   as country,
        coalesce(nullif(trim(asset_class), ''), 'Unknown') as asset_class,
        coalesce(nullif(trim(currency), ''), 'USD')      as currency,
        market_cap,
        pe_ratio,
        dividend_yield,
        beta,
        provider,
        loaded_at
    from ranked
    where recency_rank = 1

)

select
    *,
    -- Bonds, cash and commodities are what actually cushion an equity
    -- drawdown; flagging them here keeps the definition in one place.
    asset_class in ('Bond ETF', 'Cash', 'Commodity') as is_defensive,
    country = 'United States'                        as is_domestic
from cleaned
