{{ config(materialized='table') }}

{#
    Headline risk and return statistics per portfolio, with the same
    definitions the API uses so the warehouse and the app never disagree.
#}

with daily as (

    select * from {{ ref('int_portfolio_daily_returns') }}

),

drawdowns as (

    select portfolio_id, min(drawdown) as max_drawdown
    from {{ ref('mart_portfolio_performance') }}
    group by 1

),

aggregated as (

    select
        portfolio_id,
        any_value(portfolio_label)          as portfolio_label,
        any_value(benchmark)                as benchmark,
        count(*)                            as observations,
        min(price_date)                     as history_start,
        max(price_date)                     as history_end,
        stddev_samp(portfolio_return)       as daily_volatility,
        {{ compound('portfolio_return') }}  as total_return,
        quantile_cont(portfolio_return, 0.05) as var_95,
        min(portfolio_return)               as worst_day,
        max(portfolio_return)               as best_day,
        avg(case when portfolio_return > 0 then 1.0 else 0.0 end) as positive_day_rate
    from daily
    group by 1

),

downside as (

    -- Sortino's denominator: deviation of below-target days only.
    select
        portfolio_id,
        stddev_samp(portfolio_return) as downside_daily_volatility
    from daily
    where portfolio_return < {{ var('risk_free_rate') }} / {{ var('trading_days') }}
    group by 1

),

tail as (

    -- Conditional VaR: the average loss on days worse than the 5% quantile.
    select
        d.portfolio_id,
        avg(d.portfolio_return) as cvar_95
    from daily d
    join aggregated a using (portfolio_id)
    where d.portfolio_return <= a.var_95
    group by 1

)

select
    a.portfolio_id,
    a.portfolio_label,
    a.benchmark,
    a.observations,
    a.history_start,
    a.history_end,
    a.total_return,
    {{ annualize_return('a.total_return', 'a.observations') }} as annual_return,
    {{ annualize_vol('a.daily_volatility') }}                  as annual_volatility,
    {{ sharpe(
        annualize_return('a.total_return', 'a.observations'),
        annualize_vol('a.daily_volatility')
    ) }}                                                       as sharpe_ratio,
    {{ sharpe(
        annualize_return('a.total_return', 'a.observations'),
        annualize_vol('dn.downside_daily_volatility')
    ) }}                                                       as sortino_ratio,
    dd.max_drawdown,
    a.var_95,
    t.cvar_95,
    a.best_day,
    a.worst_day,
    a.positive_day_rate,
    a.observations >= {{ var('min_observations') }} as has_sufficient_history
from aggregated a
left join drawdowns dd using (portfolio_id)
left join downside dn   using (portfolio_id)
left join tail t        using (portfolio_id)
