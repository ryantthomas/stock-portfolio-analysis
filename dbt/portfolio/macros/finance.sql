{#
    Shared finance helpers so the annualization and compounding conventions
    are defined once rather than repeated across every model.
#}

{% macro annualize_vol(daily_vol_expr) %}
    ({{ daily_vol_expr }}) * sqrt({{ var('trading_days') }})
{% endmacro %}


{% macro annualize_return(total_return_expr, observation_count_expr) %}
    {#
        Compound annual growth rate from a cumulative return over N trading
        days. Guarded so a total return of -100% (or worse, from bad data)
        returns NULL instead of raising a domain error.
    #}
    case
        when ({{ observation_count_expr }}) <= 0 then null
        when (1 + ({{ total_return_expr }})) <= 0 then null
        else power(
            1 + ({{ total_return_expr }}),
            {{ var('trading_days') }}::double / ({{ observation_count_expr }})
        ) - 1
    end
{% endmacro %}


{% macro compound(return_expr) %}
    {#
        Compounded total return of a daily return column. DuckDB has no
        product aggregate, so this uses the log-sum identity. The guard keeps
        a single -100% day from producing ln(0).
    #}
    exp(sum(ln(greatest(1 + ({{ return_expr }}), 0.000001)))) - 1
{% endmacro %}


{% macro sharpe(annual_return_expr, annual_vol_expr) %}
    case
        when ({{ annual_vol_expr }}) is null or ({{ annual_vol_expr }}) <= 0 then null
        else (({{ annual_return_expr }}) - {{ var('risk_free_rate') }}) / ({{ annual_vol_expr }})
    end
{% endmacro %}


{% macro safe_divide(numerator, denominator) %}
    case
        when ({{ denominator }}) is null or ({{ denominator }}) = 0 then null
        else ({{ numerator }}) / ({{ denominator }})
    end
{% endmacro %}
