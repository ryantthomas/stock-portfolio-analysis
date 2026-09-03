{{ config(materialized='view') }}

{#
    Per-ticker summary statistics over that ticker's full available history.
    Max drawdown needs the running high-water mark, so it is computed in its
    own windowed CTE before the aggregate rolls everything up.
#}

with returns as (

    select * from {{ ref('int_daily_returns') }}

),

cumulative as (

    select
        ticker,
        price_date,
        daily_return,
        exp(sum(ln(greatest(1 + daily_return, 0.000001)))
            over (partition by ticker order by price_date)) as growth_index
    from returns

),

drawdowns as (

    select
        ticker,
        growth_index / max(growth_index) over (
            partition by ticker
            order by price_date
            rows between unbounded preceding and current row
        ) - 1 as drawdown
    from cumulative

),

max_drawdown as (

    select ticker, min(drawdown) as max_drawdown
    from drawdowns
    group by 1

),

aggregated as (

    select
        ticker,
        count(*)                        as observations,
        min(price_date)                 as history_start,
        max(price_date)                 as history_end,
        avg(daily_return)               as mean_daily_return,
        stddev_samp(daily_return)       as daily_volatility,
        {{ compound('daily_return') }}  as total_return,
        min(daily_return)               as worst_day,
        max(daily_return)               as best_day,
        avg(case when daily_return > 0 then 1.0 else 0.0 end) as positive_day_rate,
        quantile_cont(daily_return, 0.05) as var_95
    from returns
    group by 1

)

select
    a.ticker,
    a.observations,
    a.history_start,
    a.history_end,
    a.total_return,
    {{ annualize_return('a.total_return', 'a.observations') }} as annual_return,
    {{ annualize_vol('a.daily_volatility') }}                 as annual_volatility,
    {{ sharpe(
        annualize_return('a.total_return', 'a.observations'),
        annualize_vol('a.daily_volatility')
    ) }}                                                      as sharpe_ratio,
    d.max_drawdown,
    a.var_95,
    a.best_day,
    a.worst_day,
    a.positive_day_rate,
    a.observations >= {{ var('min_observations') }} as has_sufficient_history
from aggregated a
left join max_drawdown d using (ticker)
