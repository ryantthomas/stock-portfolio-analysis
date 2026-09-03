{{ config(materialized='table') }}

{#
    The opportunity rules expressed in SQL, so the same findings are available
    to anything that can query the warehouse -- a scheduled digest, a
    notebook, a BI dashboard -- and not only through the API.

    Each rule is its own CTE returning the same column shape, unioned at the
    end. Adding a check means adding one CTE and one union arm.
#}

with div as (
    select * from {{ ref('mart_portfolio_diversification') }}
),

positions as (
    select * from {{ ref('int_portfolio_positions') }}
),

risk as (
    select * from {{ ref('mart_portfolio_risk') }}
),

single_position as (

    select
        p.portfolio_id,
        'concentration-single'                                as opportunity_id,
        case when p.weight > 0.40 then 'critical' else 'warning' end as severity,
        'concentration'                                       as kind,
        p.ticker || ' is ' || round(p.weight * 100, 1) || '% of the portfolio' as title,
        'A single position this large means the portfolio''s outcome is largely '
            || p.ticker || '''s outcome.'                     as detail,
        p.weight                                              as metric
    from positions p
    where p.weight > 0.25

),

sector_concentration as (

    {#
        'Diversified' and 'Unknown' are excluded: a broad-market ETF carries
        no single-sector risk, so flagging it would be a false positive. This
        matches the rule the API applies.
    #}
    select
        portfolio_id,
        'sector-heavy'                                        as opportunity_id,
        case when sector_weight > 0.55 then 'critical' else 'warning' end as severity,
        'sector'                                              as kind,
        sector || ' is ' || round(sector_weight * 100, 1) || '% of the portfolio' as title,
        'Holdings in a single sector fall together in a sector-wide drawdown.' as detail,
        sector_weight                                         as metric
    from (
        select
            portfolio_id,
            sector,
            sum(weight) as sector_weight,
            row_number() over (partition by portfolio_id order by sum(weight) desc) as rn
        from positions
        where sector not in ('Diversified', 'Unknown')
        group by 1, 2
    )
    where rn = 1 and sector_weight > 0.40

),

low_breadth as (

    select
        portfolio_id,
        'breadth-low'                                         as opportunity_id,
        'warning'                                             as severity,
        'diversification'                                     as kind,
        'Only ' || round(1.0 / hhi, 1) || ' effective holdings' as title,
        holdings_count || ' positions, but the weighting makes them behave like far fewer.'
                                                              as detail,
        1.0 / hhi                                             as metric
    from div
    where hhi > 0 and 1.0 / hhi < 8 and holdings_count >= 3

),

high_correlation as (

    select
        portfolio_id,
        'correlation-high'                                    as opportunity_id,
        'warning'                                             as severity,
        'diversification'                                     as kind,
        'Average pairwise correlation is ' || round(avg_correlation, 2) as title,
        'The holdings largely rise and fall together, so the portfolio carries roughly '
            || 'the risk of a single bet spread across several tickers.' as detail,
        avg_correlation                                       as metric
    from div
    where avg_correlation > 0.75

),

redundancy as (

    select
        portfolio_id,
        'redundant-pairs'                                     as opportunity_id,
        'info'                                                as severity,
        'redundancy'                                          as kind,
        redundant_pairs || ' near-duplicate holding pair(s)'   as title,
        'These pairs move almost identically, so holding both adds position count '
            || 'without adding diversification.'              as detail,
        redundant_pairs::double                               as metric
    from div
    where redundant_pairs > 0

),

no_ballast as (

    select
        portfolio_id,
        'no-ballast'                                          as opportunity_id,
        'info'                                                as severity,
        'allocation'                                          as kind,
        'No bond, cash or commodity ballast'                  as title,
        'The portfolio is effectively all growth assets, with nothing to cushion an '
            || 'equity drawdown or to rebalance from when prices fall.' as detail,
        defensive_weight                                      as metric
    from div
    where defensive_weight < 0.05 and holdings_count >= 3

),

home_bias as (

    select
        portfolio_id,
        'home-bias'                                           as opportunity_id,
        'info'                                                as severity,
        'allocation'                                          as kind,
        'Exposure is essentially all domestic'                as title,
        'US assets are roughly 60% of global market capitalization; no international '
            || 'exposure is an implicit bet on continued US outperformance.' as detail,
        1 - domestic_weight                                   as metric
    from div
    where domestic_weight > 0.95 and holdings_count >= 3

),

deep_drawdown as (

    select
        portfolio_id,
        'drawdown-deep'                                       as opportunity_id,
        'warning'                                             as severity,
        'risk'                                                as kind,
        'Worst drawdown was ' || round(max_drawdown * 100, 1) || '%' as title,
        'The useful question is whether you would have held through that decline '
            || 'without selling.'                             as detail,
        max_drawdown                                          as metric
    from risk
    where max_drawdown < -0.35

),

combined as (
    select * from single_position
    union all select * from sector_concentration
    union all select * from low_breadth
    union all select * from high_correlation
    union all select * from redundancy
    union all select * from no_ballast
    union all select * from home_bias
    union all select * from deep_drawdown
)

select
    portfolio_id,
    opportunity_id,
    severity,
    kind,
    title,
    detail,
    metric,
    case severity when 'critical' then 1 when 'warning' then 2 else 3 end as severity_rank
from combined
order by portfolio_id, severity_rank, metric desc
