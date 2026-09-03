{{ config(materialized='table') }}

{#
    The diversification picture in one row per portfolio: concentration
    (Herfindahl and effective holdings), how correlated the holdings actually
    are, and how much volatility reduction the combination bought.

    The diversification ratio compares the weighted average volatility of the
    holdings to the realized volatility of the portfolio. A ratio near 1 means
    the positions all move together and combining them achieved nothing.
#}

with positions as (

    select * from {{ ref('int_portfolio_positions') }}

),

concentration as (

    select
        portfolio_id,
        any_value(portfolio_label) as portfolio_label,
        max(created_at)            as created_at,
        count(*)                  as holdings_count,
        sum(power(weight, 2))     as hhi,
        max(weight)               as top_weight,
        count(distinct sector)    as sector_count,
        count(distinct asset_class) as asset_class_count,
        count(distinct country)   as country_count,
        sum(case when is_defensive then weight else 0 end) as defensive_weight,
        sum(case when is_domestic  then weight else 0 end) as domestic_weight,
        sum(weighted_volatility)  as weighted_avg_volatility
    from positions
    group by 1

),

top_five as (

    select
        portfolio_id,
        sum(weight) as top5_weight
    from (
        select
            portfolio_id,
            weight,
            row_number() over (partition by portfolio_id order by weight desc) as rn
        from positions
    )
    where rn <= 5
    group by 1

),

sector_concentration as (

    select
        portfolio_id,
        sum(power(sector_weight, 2)) as sector_hhi,
        max(sector_weight)           as top_sector_weight
    from (
        select portfolio_id, sector, sum(weight) as sector_weight
        from positions
        group by 1, 2
    )
    group by 1

),

correlations as (

    -- Weighted by the product of the two position sizes, so a pair of tiny
    -- holdings that move together does not distort the headline number.
    select
        c.portfolio_id,
        {{ safe_divide(
            'sum(c.correlation * ha.weight * hb.weight)',
            'sum(ha.weight * hb.weight)'
        ) }}                        as avg_correlation,
        max(c.correlation)          as max_correlation,
        min(c.correlation)          as min_correlation,
        count(*)                    as pair_count,
        sum(case when c.correlation >= 0.85 then 1 else 0 end) as redundant_pairs
    from {{ ref('int_pair_correlations') }} c
    join positions ha on ha.portfolio_id = c.portfolio_id and ha.ticker = c.ticker_a
    join positions hb on hb.portfolio_id = c.portfolio_id and hb.ticker = c.ticker_b
    group by 1

)

select
    c.portfolio_id,
    c.portfolio_label,
    c.created_at,
    c.holdings_count,
    c.hhi,
    {{ safe_divide('1.0', 'c.hhi') }}      as effective_holdings,
    c.top_weight,
    t.top5_weight,
    c.sector_count,
    c.asset_class_count,
    c.country_count,
    s.sector_hhi,
    s.top_sector_weight,
    c.defensive_weight,
    c.domestic_weight,
    r.avg_correlation,
    r.max_correlation,
    r.min_correlation,
    r.pair_count,
    coalesce(r.redundant_pairs, 0)        as redundant_pairs,
    c.weighted_avg_volatility,
    pr.annual_volatility                  as portfolio_volatility,
    {{ safe_divide('c.weighted_avg_volatility', 'pr.annual_volatility') }}
                                          as diversification_ratio,
    -- Volatility actually saved by combining these positions rather than
    -- holding them as independent bets.
    c.weighted_avg_volatility - pr.annual_volatility as volatility_reduction

from concentration c
left join top_five t              using (portfolio_id)
left join sector_concentration s  using (portfolio_id)
left join correlations r          using (portfolio_id)
left join {{ ref('mart_portfolio_risk') }} pr using (portfolio_id)
