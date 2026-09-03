{{ config(materialized='view') }}

{#
    Every position enriched with its security metadata and its own risk and
    return statistics. This is the join that the allocation, performance and
    diversification marts all build on.
#}

select
    h.portfolio_id,
    h.portfolio_label,
    h.benchmark,
    h.ticker,
    h.weight,
    h.created_at,

    coalesce(s.security_name, h.ticker) as security_name,
    coalesce(s.sector, 'Unknown')       as sector,
    coalesce(s.industry, 'Unknown')     as industry,
    coalesce(s.country, 'Unknown')      as country,
    coalesce(s.asset_class, 'Unknown')  as asset_class,
    coalesce(s.currency, 'USD')         as currency,
    coalesce(s.is_defensive, false)     as is_defensive,
    coalesce(s.is_domestic, false)      as is_domestic,
    s.market_cap,
    s.pe_ratio,
    s.dividend_yield,
    s.beta,

    st.observations,
    st.total_return,
    st.annual_return,
    st.annual_volatility,
    st.sharpe_ratio,
    st.max_drawdown,
    st.has_sufficient_history,

    -- Weight times return: how much of the portfolio's result this position
    -- actually produced, rather than how it performed in isolation.
    h.weight * st.total_return as contribution_to_return,
    -- Weight times volatility. A true risk contribution needs the full
    -- covariance matrix (the API computes that); this is the standalone
    -- approximation, useful for ranking positions by risk footprint.
    h.weight * st.annual_volatility as weighted_volatility

from {{ ref('stg_portfolio_holdings') }} h
left join {{ ref('stg_securities') }} s    on s.ticker = h.ticker
left join {{ ref('int_security_stats') }} st on st.ticker = h.ticker
