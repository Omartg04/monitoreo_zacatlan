"""
CEOP · transform_zacatlan.py
Extracción + transformación para la base de Zacatlán (Encuesta L2).

Reutiliza la paginación genérica de bubble_connector.py (_fetch_pages,
_fetch_single_page) y normalizar_nombre — son agnósticas al cuestionario y
ya leen BUBBLE_ENDPOINT/BUBBLE_PAGE_SIZE desde config.py (este config.py,
el de Zacatlán). Lo que SÍ es específico de esta base y se reescribe aquí:

  - Constraints de fecha (INICIO_OPERATIVO = 2026-06-13, no 2026-04-17)
  - _transform(): FIELD_MAP de 126 campos, sin equivalente a p11_* de Guerrero
  - encuestador_id: usa `user_creador` (Created By) desde el día 1 — en L2
    Bubble ya tiene login activo, no aplica el cutover INICIO_LOGIN_BUBBLE
  - `equipo`: derivado de seccion_electoral vía METAS_POR_SECCION (no viene
    en el registro de la encuesta)
  - `terminada`: heurística por completitud del Bloque 10 (ver TODO abajo)

Uso:
    from transform_zacatlan import get_encuestas
    df, ultima_act = get_encuestas(api_key="...", equipos=["Areli"])
"""
import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from bubble_connector import _fetch_pages, normalizar_nombre  # reutilizado — agnóstico al cuestionario
from config import (
    CACHE_TTL_SEC, FIELD_MAP, INICIO_OPERATIVO, METAS_POR_SECCION,
)

logger = logging.getLogger(__name__)

_ISO_FMT = "%Y-%m-%dT%H:%M:%S.000Z"
_CORTE_OPERATIVO = (pd.Timestamp(INICIO_OPERATIVO) - pd.Timedelta(seconds=1)).strftime(_ISO_FMT)


# ── Paginación con constraints de Zacatlán ────────────────────────────────────

def _fetch_all_raw(api_key: str) -> list[dict]:
    """Carga completa desde el inicio del operativo (13 junio 2026)."""
    return _fetch_pages(api_key, [
        {
            "key":             "Created Date",
            "constraint_type": "greater than",
            "value":           _CORTE_OPERATIVO,
        },
    ])


def _fetch_delta_raw(api_key: str, desde: datetime) -> list[dict]:
    """
    Carga incremental: registros creados O modificados después de `desde`.
    Bubble no soporta OR nativo → dos consultas + deduplicación por _id.
    """
    ts_str = desde.strftime(_ISO_FMT)
    base = {
        "key":             "Created Date",
        "constraint_type": "greater than",
        "value":           _CORTE_OPERATIVO,
    }

    nuevos = _fetch_pages(api_key, [base,
        {"key": "Created Date",  "constraint_type": "greater than", "value": ts_str}])
    modificados = _fetch_pages(api_key, [base,
        {"key": "Modified Date", "constraint_type": "greater than", "value": ts_str}])

    seen: dict[str, dict] = {}
    for r in nuevos + modificados:
        rid = r.get("_id", "")
        if rid not in seen:
            seen[rid] = r
        else:
            if r.get("Modified Date", "") > seen[rid].get("Modified Date", ""):
                seen[rid] = r

    return list(seen.values())


# ── Transformación ─────────────────────────────────────────────────────────────

# TODO: confirmar si Bubble expone un campo de estatus explícito para Zacatlán
# (p.ej. "estatus_encuesta" / "respuesta_completa"). Si existe, agregarlo a
# FIELD_MAP y usarlo aquí en lugar de la heurística por completitud.
_CAMPO_ESTATUS_CANDIDATOS = ["estatus_encuesta", "estatus", "respuesta_completa", "completada"]


def _detectar_terminada(r: dict, row: dict) -> bool:
    for campo in _CAMPO_ESTATUS_CANDIDATOS:
        if campo in r:
            val = str(r.get(campo, "")).strip().lower()
            return val in ("terminada", "completa", "completada", "true", "yes", "sí", "si")
    # Heurística: si respondió la última pregunta del cuestionario (Bloque 10,
    # P22_3 = aprobación de la presidenta), se considera entrevista completa.
    return bool(row.get("aprobacion_presidenta")) and str(row.get("aprobacion_presidenta")).strip() != ""


def _transform(records: list[dict]) -> pd.DataFrame:
    """Aplica FIELD_MAP, deriva duracion_min, encuestador_id, equipo, terminada."""
    rows = []
    for r in records:
        row = {}
        for bubble_key, app_key in FIELD_MAP.items():
            row[app_key] = r.get(bubble_key)
        row["_created_by"] = r.get("Created By", "")
        row["terminada"] = _detectar_terminada(r, row)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["folio"] = df["id_unico"]

    for col in ("fecha_creacion", "fecha_modificacion"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    df["duracion_min"] = (
        (df["fecha_modificacion"] - df["fecha_creacion"])
        .dt.total_seconds().div(60).round(1)
    )
    # Sin lotes de carga manual identificados aún para Zacatlán — todo confiable.
    # TODO: si se detecta un día de carga por lote (como FECHA_BATCH_MANUAL en
    # Guerrero), excluirlo aquí con duracion_confiable = False.
    df["duracion_confiable"] = True

    df["fecha"] = df["fecha_creacion"].dt.tz_convert("America/Mexico_City").dt.date

    df["seccion_electoral"] = pd.to_numeric(df["seccion_electoral"], errors="coerce").astype("Int64")
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce").astype("Int64")
    for col in ("latitud", "longitud"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["municipio_texto"] = df["municipio_texto"].astype(str).str.strip().str.upper()
    df["nombre_encuestador"] = df["nombre_encuestador"].apply(normalizar_nombre)

    def _enc_id(row):
        cb = str(row.get("_created_by", "")).strip()
        if cb and cb not in ("", "None"):
            return cb
        return str(abs(hash(row["nombre_encuestador"])))

    df["encuestador_id"] = df.apply(_enc_id, axis=1)
    df["encuestador_nombre"] = df["nombre_encuestador"]
    df.drop(columns=["_created_by", "nombre_encuestador"], inplace=True)

    df["equipo"] = df["seccion_electoral"].apply(
        lambda s: METAS_POR_SECCION.get(int(s), {}).get("equipo", "Sin asignar") if pd.notna(s) else "Sin asignar"
    )

    return df


# ── Merge incremental (reutiliza patrón de bubble_connector, clave = folio) ────

def _merge_delta(df_base: pd.DataFrame, df_delta: pd.DataFrame) -> pd.DataFrame:
    if df_delta.empty:
        return df_base
    if df_base.empty:
        return df_delta
    folios_delta = set(df_delta["folio"])
    return pd.concat(
        [df_base[~df_base["folio"].isin(folios_delta)], df_delta],
        ignore_index=True,
    )


# ── Caché global ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def _load_full(api_key: str) -> tuple[pd.DataFrame, float]:
    raw = _fetch_all_raw(api_key)
    df = _transform(raw)
    return df, time.time()


@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def _load_delta(api_key: str, desde_ts: float) -> tuple[pd.DataFrame, float]:
    desde_dt = datetime.fromtimestamp(desde_ts, tz=timezone.utc)
    raw = _fetch_delta_raw(api_key, desde_dt)
    df_delta = _transform(raw) if raw else pd.DataFrame()
    return df_delta, time.time()


# ── Función pública ───────────────────────────────────────────────────────────

def get_encuestas(
    api_key: str,
    equipos: list[str] | None = None,
    secciones: list[int] | None = None,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, datetime | None]:
    """
    Retorna (df, ultima_actualizacion). Mismo patrón que bubble_connector.get_encuestas:
    carga completa + delta cacheados globalmente, filtros en memoria.

    `equipos`: filtra por config.SECCIONES_POR_EQUIPO (ej. ["Areli","Mayra"]).
    `secciones`: filtra por número de sección electoral.
    """
    if force_refresh:
        _load_full.clear()
        _load_delta.clear()

    try:
        df_base, ts_base = _load_full(api_key)
        df_delta, ts_delta = _load_delta(api_key, ts_base)

        if not df_delta.empty:
            df = _merge_delta(df_base, df_delta)
            ts_ok = ts_delta
        else:
            df = df_base
            ts_ok = ts_base

    except Exception as e:
        logger.warning("Error cargando desde Bubble: %s. Devolviendo DataFrame vacío.", e)
        cols = list(FIELD_MAP.values()) + [
            "folio", "duracion_min", "fecha", "encuestador_id", "encuestador_nombre",
            "equipo", "terminada",
        ]
        return pd.DataFrame(columns=cols), None

    if secciones:
        df = df[df["seccion_electoral"].isin(secciones)].copy()
    if equipos:
        df = df[df["equipo"].isin(equipos)].copy()

    return df, _ts_to_dt(ts_ok)


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)
