from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import MySQLdb.cursors


@dataclass
class TractorStateAgent:
    """Agente MaSe para resolver estado de tractor por serie."""

    db_conn: object

    @property
    def name(self) -> str:
        return "MaSeTractorStateAgent"

    def _dict_cursor(self):
        return self.db_conn.cursor(MySQLdb.cursors.DictCursor)

    def resolve_tractor(self, serie: str) -> Optional[Dict[str, object]]:
        cur = self._dict_cursor()
        try:
            cur.execute(
                """
                SELECT
                    id,
                    serie,
                    equipo,
                    modelo,
                    estado,
                    situacion
                FROM tractor
                WHERE UPPER(TRIM(serie)) = UPPER(TRIM(%s))
                LIMIT 1
                """,
                (serie,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    def get_preparacion_states(self, tractor_id: int) -> List[Dict[str, str]]:
        cur = self._dict_cursor()
        try:
            cur.execute(
                """
                SELECT
                    codigo_req,
                    requerimiento,
                    estado,
                    id
                FROM mantenimientos
                WHERE tractor_id = %s
                  AND LOWER(TRIM(requerimiento)) = 'preparacion'
                ORDER BY id DESC
                """,
                (tractor_id,),
            )
            rows = cur.fetchall() or []
        finally:
            cur.close()

        results: List[Dict[str, str]] = []
        for row in rows:
            results.append(
                {
                    "codigo_req": (row.get("codigo_req") or "").strip(),
                    "requerimiento": (row.get("requerimiento") or "").strip(),
                    "estado": (row.get("estado") or "").strip(),
                }
            )
        return results

    def run(self, serie: str) -> Dict[str, object]:
        serie_clean = (serie or "").strip()
        if not serie_clean:
            return {
                "ok": False,
                "message": "Debe ingresar una serie.",
                "agent": self.name,
            }

        tractor = self.resolve_tractor(serie_clean)
        if not tractor:
            return {
                "ok": False,
                "message": "No se encontro tractor para la serie ingresada.",
                "agent": self.name,
            }

        items = self.get_preparacion_states(int(tractor["id"]))

        return {
            "ok": True,
            "agent": self.name,
            "serie": (tractor.get("serie") or serie_clean).strip(),
            "items": items,
            "tractor": {
                "equipo": (tractor.get("equipo") or "").strip(),
                "modelo": (tractor.get("modelo") or "").strip(),
                "estado": (tractor.get("estado") or tractor.get("situacion") or "").strip(),
            },
        }
