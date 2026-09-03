{{ config(materialized='table') }}

{#
    Symmetric correlation matrix in long form: both (a,b) and (b,a) plus the
    diagonal, so a heatmap can read it directly without pivoting or having to
    mirror the upper triangle itself.
#}

with pairs as (

    select
        portfolio_id, ticker_a, ticker_b, correlation, covariance, overlapping_days
    from {{ ref('int_pair_correlations') }}

),

mirrored as (

    select portfolio_id, ticker_a, ticker_b, correlation, covariance, overlapping_days
    from pairs

    union all

    select portfolio_id, ticker_b, ticker_a, correlation, covariance, overlapping_days
    from pairs

    union all

    -- The diagonal: every security correlates perfectly with itself.
    select
        portfolio_id,
        ticker      as ticker_a,
        ticker      as ticker_b,
        1.0         as correlation,
        null        as covariance,
        null        as overlapping_days
    from {{ ref('stg_portfolio_holdings') }}

)

select
    portfolio_id,
    ticker_a,
    ticker_b,
    correlation,
    covariance,
    overlapping_days,
    case
        when ticker_a = ticker_b        then 'self'
        when correlation >= 0.85        then 'redundant'
        when correlation >= 0.60        then 'high'
        when correlation >= 0.30        then 'moderate'
        when correlation >= 0.00        then 'low'
        else 'negative'
    end as correlation_band
from mirrored
