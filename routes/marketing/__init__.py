"""Marketing module compatibility facade.

This file keeps the original import path routes.marketing stable while the
implementation is split into focused modules.
"""

from routes.marketing.shared import (
    CAMPAIGN_CHANNELS,
    CHANNEL_LEAD_NAME_FILTERS,
    DEPARTAMENTOS,
    Decimal,
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _append_channel_filter,
    _calculate_growth,
    _campaign_financial_snapshot,
    _column_exists,
    _count_closed_sales_by_year,
    _count_leads_by_year,
    _fetch_facebook_followers,
    _fetch_instagram_followers,
    _fetch_instagram_followers_with_fallback,
    _get_linea_familia_options,
    _get_linea_producto_options,
    _get_lineas_negocio_options,
    _get_previous_year_value,
    _graph_api_get,
    _last_year_date,
    _latest_seguimiento_subquery,
    _load_social_metrics_history,
    _marketing_before_request,
    _marketing_scope_clause,
    _resolve_line_selection,
    _resolve_negocio_id_by_brand,
    _resolve_ubigeo_name,
    _safe_decimal,
    _save_feria_kpi_snapshot,
    _save_social_metrics_snapshot,
    _sum_marketing_investment_by_year,
    _table_exists,
    _to_decimal,
    _to_int,
    flash,
    jsonify,
    login_required,
    marketing_bp,
    mysql,
    obtener_nombre_departamento,
    redirect,
    render_template,
    request,
    role_required,
    secure_filename,
    session,
    url_for,
)

from routes.marketing.clients import marketing_clientes  # noqa: F401
from routes.marketing.okr_panel import marketing_okr  # noqa: F401
from routes.marketing.shared import marketing_lineas_producto_underscore_api  # noqa: F401
from routes.marketing.whatsapp import (  # noqa: F401
    marketing_api_config,
    marketing_upload_image,
)

# Import side effects register routes on the shared blueprint.
from routes.marketing import campana  # noqa: F401
from routes.marketing import feria  # noqa: F401
from routes.marketing import inventario  # noqa: F401
from routes.marketing import roadmap  # noqa: F401

