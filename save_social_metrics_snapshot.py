#!/usr/bin/env python3
"""Daily snapshot script for marketing social metrics.

This script reads brand-specific Graph API credentials from environment variables
and saves a daily snapshot to marketing_social_metrics for each business.

Usage:
  python save_social_metrics_snapshot.py --brands orbes lovol
  python save_social_metrics_snapshot.py --all
"""

import argparse
import os
from datetime import date

from app import create_app
from extensions import mysql
from MySQLdb.cursors import DictCursor
from routes.marketing import (
    _fetch_facebook_followers,
    _fetch_instagram_followers,
    _resolve_negocio_id_by_brand,
    _save_social_metrics_snapshot,
    _table_exists,
    _to_int,
)

DEFAULT_BRANDS = ["orbes", "lovol"]


def _get_brand_settings(brand_slug):
    prefix = brand_slug.upper()
    return {
        "brand": brand_slug,
        "meta_token": os.getenv(f"{prefix}_META_ACCESS_TOKEN", "").strip(),
        "api_version": os.getenv(f"{prefix}_META_API_VERSION", os.getenv(f"{prefix}_WA_API_VERSION", "v20.0")).strip() or "v20.0",
        "fb_page_id": os.getenv(f"{prefix}_FB_PAGE_ID", "").strip(),
        "ig_account_id": os.getenv(f"{prefix}_IG_ACCOUNT_ID", "").strip(),
        "fb_target": _to_int(os.getenv(f"{prefix}_FB_TARGET_FOLLOWERS", "").strip()),
        "ig_target": _to_int(os.getenv(f"{prefix}_IG_TARGET_FOLLOWERS", "").strip()),
    }


def _resolve_db_brand_slugs():
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT DISTINCT LOWER(TRIM(slug)) AS slug FROM negocios WHERE slug IS NOT NULL")
        rows = cur.fetchall() or []
        return [row["slug"] for row in rows if row.get("slug")]
    finally:
        cur.close()


def _process_brand(brand_slug):
    settings = _get_brand_settings(brand_slug)
    meta_token = settings["meta_token"]
    api_version = settings["api_version"]
    fb_page_id = settings["fb_page_id"]
    ig_account_id = settings["ig_account_id"]
    fb_target = settings["fb_target"]
    ig_target = settings["ig_target"]

    if not meta_token:
        return {
            "brand": brand_slug,
            "status": "skipped",
            "message": "Falta META_ACCESS_TOKEN",
        }

    if not fb_page_id and not ig_account_id:
        return {
            "brand": brand_slug,
            "status": "skipped",
            "message": "No hay FB_PAGE_ID ni IG_ACCOUNT_ID configurados",
        }

    negocio_id = _resolve_negocio_id_by_brand(brand_slug)
    if not negocio_id:
        return {
            "brand": brand_slug,
            "status": "error",
            "message": "No se pudo resolver negocio_id desde negocios.slug",
        }

    results = []
    fb_data = None
    ig_data = None

    if fb_page_id:
        fb_data = _fetch_facebook_followers(fb_page_id, meta_token, api_version)
        results.append(("Facebook", fb_data))

    if ig_account_id:
        ig_data = _fetch_instagram_followers(ig_account_id, meta_token, api_version)
        results.append(("Instagram", ig_data))

    errors = [f"{name}: {data['error']}" for name, data in results if data and data.get("error")]
    if errors:
        return {
            "brand": brand_slug,
            "status": "error",
            "message": "; ".join(errors),
        }

    current_total = 0
    if fb_data and fb_data.get("current") is not None:
        current_total += fb_data["current"]
    if ig_data and ig_data.get("current") is not None:
        current_total += ig_data["current"]

    saved = _save_social_metrics_snapshot(
        negocio_id=negocio_id,
        snapshot_date=date.today(),
        fb_page_id=fb_page_id or None,
        ig_account_id=ig_account_id or None,
        fb_followers=fb_data.get("current") if fb_data else None,
        ig_followers=ig_data.get("current") if ig_data else None,
        total_followers=current_total,
        fb_target=fb_target,
        ig_target=ig_target,
        total_target=(fb_target or 0) + (ig_target or 0),
    )

    return {
        "brand": brand_slug,
        "status": "saved" if saved else "error",
        "message": "Snapshot guardado" if saved else "No se pudo guardar snapshot",
        "fb_followers": fb_data.get("current") if fb_data else None,
        "ig_followers": ig_data.get("current") if ig_data else None,
        "total_followers": current_total,
        "fb_target": fb_target,
        "ig_target": ig_target,
    }


def main():
    parser = argparse.ArgumentParser(description="Guardar snapshot diario de métricas sociales por negocio")
    parser.add_argument("--brands", nargs="*", help="Lista de marcas a procesar (ej. orbes lovol)")
    parser.add_argument("--all", action="store_true", help="Procesar todas las marcas encontradas en la tabla negocios")
    args = parser.parse_args()

    if args.all:
        brands = _resolve_db_brand_slugs()
    elif args.brands:
        brands = [brand.strip().lower() for brand in args.brands if brand.strip()]
    else:
        brands = DEFAULT_BRANDS

    if not brands:
        print("No se encontraron marcas para procesar.")
        return 1

    app = create_app()
    with app.app_context():
        if not _table_exists("marketing_social_metrics"):
            print("La tabla marketing_social_metrics no existe. Ejecuta la migración primero.")
            return 1

        all_ok = True
        print("Guardando snapshots de métricas sociales:\n")
        for brand in brands:
            result = _process_brand(brand)
            status = result["status"]
            line = f"- {brand}: {status}. {result.get('message', '')}"
            if status == "saved":
                line += f" (FB={result.get('fb_followers')} IG={result.get('ig_followers')} total={result.get('total_followers')})"
            print(line)
            if status != "saved":
                all_ok = False

        return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
