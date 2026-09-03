{#
    Use the custom schema name verbatim instead of dbt's default of
    prefixing it with the target schema. That gives clean `staging`,
    `intermediate` and `marts` schemas alongside the API's `raw` schema,
    rather than `main_staging` and friends.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
