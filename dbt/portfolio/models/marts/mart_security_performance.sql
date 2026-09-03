{{ config(materialized='table') }}

{#
    One row per security with its performance, risk and descriptive data
    joined together -- the security-level reference table for ad-hoc analysis.
#}

select
    s.ticker,
    s.security_name,
    s.sector,
    s.industry,
    s.country,
    s.asset_class,
    s.currency,
    s.is_defensive,
    s.is_domestic,
    s.market_cap,
    s.pe_ratio,
    s.dividend_yield,
    s.beta,

    st.observations,
    st.history_start,
    st.history_end,
    st.total_return,
    st.annual_return,
    st.annual_volatility,
    st.sharpe_ratio,
    st.max_drawdown,
    st.var_95,
    st.best_day,
    st.worst_day,
    st.positive_day_rate,
    st.has_sufficient_history,

    p.adj_close as latest_price

from {{ ref('stg_securities') }} s
left join {{ ref('int_security_stats') }} st on st.ticker = s.ticker
left join (
    select ticker, adj_close,
           row_number() over (partition by ticker order by price_date desc) as rn
    from {{ ref('stg_prices') }}
) p on p.ticker = s.ticker and p.rn = 1
