{{ config(materialized='table') }}

{#
    Allocation unpivoted into one long table across every grouping dimension,
    so a BI tool can pivot on `dimension` instead of needing a separate model
    per breakdown.
#}

with positions as (

    select * from {{ ref('int_portfolio_positions') }}

),

by_dimension as (

    select portfolio_id, 'sector'      as dimension, sector      as bucket, weight, ticker from positions
    union all
    select portfolio_id, 'asset_class' as dimension, asset_class as bucket, weight, ticker from positions
    union all
    select portfolio_id, 'country'     as dimension, country     as bucket, weight, ticker from positions
    union all
    select portfolio_id, 'industry'    as dimension, industry    as bucket, weight, ticker from positions
    union all
    select portfolio_id, 'ticker'      as dimension, ticker      as bucket, weight, ticker from positions

)

select
    portfolio_id,
    dimension,
    bucket,
    sum(weight)                       as weight,
    count(distinct ticker)            as position_count,
    list(distinct ticker)             as tickers,
    row_number() over (
        partition by portfolio_id, dimension order by sum(weight) desc
    ) as weight_rank
from by_dimension
group by 1, 2, 3
