"""
CEOP · bubble_connector.py
Carga paginada desde la Data API de Bubble con caché global y carga incremental.

Cambios vs v8 (15 mayo 2026):
  - Caché global: @st.cache_data(ttl=CACHE_TTL_SEC) reemplaza st.session_state.
    Un solo ciclo de refresh compartido entre todas las sesiones activas.
  - TTL: 3600 s (1 hora). El botón force_refresh cubre necesidades inmediatas.
  - Carga incremental: _fetch_delta_raw() trae solo registros nuevos/modificados
    desde el último timestamp conocido y los mergea con el caché existente.
    La primera carga del día sigue siendo completa (sin caché previo).

Uso:
    from bubble_connector import get_encuestas
    df, ultima_act = get_encuestas(api_key="...", municipios=["ACAPULCO DE JUAREZ"])
"""
import json
import time
import logging
import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st

from config import (
    BUBBLE_ENDPOINT, BUBBLE_PAGE_SIZE,
    CACHE_TTL_SEC, FIELD_MAP, CAMPOS_EXCLUIR,
)

logger = logging.getLogger(__name__)

# ── Constantes de corte temporal ──────────────────────────────────────────────
INICIO_OPERATIVO    = pd.Timestamp("2026-04-18").date()
FECHA_BATCH_MANUAL  = pd.Timestamp("2026-04-19").date()
INICIO_LOGIN_BUBBLE = pd.Timestamp("2026-04-25").date()

_ISO_FMT = "%Y-%m-%dT%H:%M:%S.000Z"


# ── Normalización de nombres ───────────────────────────────────────────────────

def normalizar_nombre(s: str | None) -> str:
    """
    Normalización agresiva para colapsar variantes del mismo nombre.
    strip → mayúsculas → quitar acentos → solo ASCII → espacios múltiples → 1.
    """
    if not s or str(s).strip() in ("", "None", "nan"):
        return "SIN NOMBRE"
    s = str(s).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "SIN NOMBRE"


# ── Paginación bruta ───────────────────────────────────────────────────────────

MAX_WORKERS = 10  # hilos paralelos — no superar 15 con Bubble


def _fetch_single_page(api_key: str, constraints: list[dict], cursor: int) -> tuple[int, list[dict]]:
    """
    Descarga una sola página con back-off exponencial (máx 3 intentos).
    Devuelve (cursor, resultados) para poder reensamblar en orden.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    params  = {
        "limit":       BUBBLE_PAGE_SIZE,
        "cursor":      cursor,
        "constraints": json.dumps(constraints),
    }
    for intento in range(3):
        try:
            resp = requests.get(BUBBLE_ENDPOINT, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("response", {}).get("results", [])
            return cursor, results
        except requests.RequestException as e:
            if intento == 2:
                logger.error("Bubble API error en cursor %d tras 3 intentos: %s", cursor, e)
                raise
            time.sleep(2 ** (intento + 1))
    return cursor, []  # nunca llega aquí


def _fetch_pages(api_key: str, constraints: list[dict]) -> list[dict]:
    """
    Descarga todas las páginas de Bubble que cumplan los constraints dados.

    Estrategia:
    1. Página 0 en serie → obtiene `remaining` real y primeros registros.
    2. Calcula cursores restantes usando remaining (no count — count es el
       total de la tabla sin filtros y no sirve para calcular páginas).
    3. Lanza todas las páginas restantes en paralelo (MAX_WORKERS hilos).
    4. Reensambla en orden de cursor para reproducibilidad.

    Con 29K registros y 10 hilos: ~25-40 seg en red celular vs ~4 min en serie.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    # — Página 0 en serie para obtener remaining real —
    resp0 = requests.get(
        BUBBLE_ENDPOINT,
        headers=headers,
        params={"limit": BUBBLE_PAGE_SIZE, "cursor": 0, "constraints": json.dumps(constraints)},
        timeout=15,
    )
    resp0.raise_for_status()
    body0     = resp0.json().get("response", {})
    results   = body0.get("results", [])
    remaining = body0.get("remaining", 0)
    total_est = len(results) + remaining

    print(f"  Bubble: {len(results)}/{total_est} registros...", flush=True)

    if remaining == 0:
        return results

    # — Cursores restantes basados en remaining —
    cursors = list(range(BUBBLE_PAGE_SIZE, total_est, BUBBLE_PAGE_SIZE))

    # — Descarga paralela —
    pages: dict[int, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_single_page, api_key, constraints, c): c
            for c in cursors
        }
        for future in as_completed(futures):
            cursor, page_results = future.result()
            pages[cursor] = page_results

    print(f"  Bubble: {total_est}/{total_est} registros OK", flush=True)

    # — Reensamble en orden —
    for cursor in sorted(pages.keys()):
        results.extend(pages[cursor])

    return results


def _fetch_all_raw(api_key: str) -> list[dict]:
    """Carga completa desde el inicio del operativo."""
    return _fetch_pages(api_key, [
        {
            "key":              "Created Date",
            "constraint_type": "greater than",
            "value":           "2026-04-17T23:59:59.000Z",
        },
    ])


def _fetch_delta_raw(api_key: str, desde: datetime) -> list[dict]:
    """
    Carga incremental: registros creados O modificados después de `desde`.
    Bubble no soporta OR nativo → dos consultas + deduplicación por _id.
    Modified Date siempre gana en caso de colisión (registro más fresco).
    """
    ts_str = desde.strftime(_ISO_FMT)
    base   = {
        "key":              "Created Date",
        "constraint_type": "greater than",
        "value":           "2026-04-17T23:59:59.000Z",
    }

    nuevos      = _fetch_pages(api_key, [base,
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


# ── Transformación y limpieza ──────────────────────────────────────────────────

def _transform(records: list[dict]) -> pd.DataFrame:
    """
    Aplica FIELD_MAP, excluye PII, deriva duracion_min, normaliza tipos.
    """
    rows = []
    for r in records:
        row = {}
        for bubble_key, app_key in FIELD_MAP.items():
            row[app_key] = r.get(bubble_key)
        row["tiene_celular"]     = bool(r.get("celular_encuestado"))
        row["tiene_correo"]      = bool(r.get("email_encuestado"))
        row["encuestador_email"] = r.get("email_encuestador", "")
        row["_created_by"]       = r.get("Created By", "")
        rows.append(row)

    df = pd.DataFrame(rows)

    for col in ("fecha_inicio", "fecha_fin"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    df["duracion_min"] = (
        (df["fecha_fin"] - df["fecha_inicio"])
        .dt.total_seconds().div(60).round(1)
    )

    df["fecha"] = df["fecha_inicio"].dt.tz_convert("America/Mexico_City").dt.date
    df = df[df["fecha"] >= INICIO_OPERATIVO].copy()

    df["duracion_confiable"] = df["fecha"] != FECHA_BATCH_MANUAL

    df["seccion"] = pd.to_numeric(df["seccion"], errors="coerce").astype("Int64")
    df["edad"]    = pd.to_numeric(df["edad"],    errors="coerce").astype("Int64")

    df["terminada"]  = df["estatus"].astype(str).str.strip() == "Terminada"
    df["municipio"]  = df["municipio"].str.strip().str.upper()
    df["encuestador_nombre"] = df["encuestador_nombre"].apply(normalizar_nombre)

    def _enc_id(row):
        if row["fecha"] is not None and row["fecha"] >= INICIO_LOGIN_BUBBLE:
            cb = str(row.get("_created_by", "")).strip()
            if cb and cb not in ("", "None"):
                return cb
        return str(abs(hash(row["encuestador_nombre"])))

    df["encuestador_id"] = df.apply(_enc_id, axis=1)
    df.drop(columns=["_created_by"], inplace=True)

    p11_cols = [
        "p11_programas_sociales", "p11_empleo", "p11_seguridad",
        "p11_educacion", "p11_salud", "p11_infraestructura", "p11_otra",
    ]
    for col in p11_cols:
        if col in df.columns:
            df[col] = df[col].notna() & (df[col].astype(str).str.strip() != "")

    return df


# ── Merge incremental ──────────────────────────────────────────────────────────

def _merge_delta(df_base: pd.DataFrame, df_delta: pd.DataFrame) -> pd.DataFrame:
    """
    Fusiona df_delta sobre df_base por `folio`.
    Registros del delta reemplazan a los del base (pueden haber cambiado estatus).
    Registros nuevos se agregan al final.
    """
    if df_delta.empty:
        return df_base
    if df_base.empty:
        return df_delta
    folios_delta = set(df_delta["folio"])
    return pd.concat(
        [df_base[~df_base["folio"].isin(folios_delta)], df_delta],
        ignore_index=True,
    )


# ── Caché global con @st.cache_data ───────────────────────────────────────────
# Compartido entre todas las sesiones. Un solo ciclo de refresh por TTL.
# El filtro por municipio se aplica en memoria después, sin llamadas adicionales.

@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def _load_full(api_key: str) -> tuple[pd.DataFrame, float]:
    """Carga completa desde Bubble. Resultado compartido entre sesiones."""
    raw = _fetch_all_raw(api_key)
    df  = _transform(raw)
    return df, time.time()


@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False)
def _load_delta(api_key: str, desde_ts: float) -> tuple[pd.DataFrame, float]:
    """
    Carga incremental desde `desde_ts` (Unix timestamp).
    También cacheada globalmente — solo llama a Bubble cuando su propio
    caché expira, evitando llamadas redundantes entre sesiones.
    """
    desde_dt = datetime.fromtimestamp(desde_ts, tz=timezone.utc)
    raw      = _fetch_delta_raw(api_key, desde_dt)
    df_delta = _transform(raw) if raw else pd.DataFrame()
    return df_delta, time.time()


# ── Función pública ────────────────────────────────────────────────────────────

def get_encuestas(
    api_key: str,
    municipios: list[str] | None = None,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, datetime | None]:
    """
    Retorna (df, ultima_actualizacion).

    Estrategia de carga:
    1. Sin caché → carga completa (_load_full).
    2. Caché vigente → devuelve resultado cacheado sin llamar a Bubble.
    3. Caché expirado → _load_full recarga completo (gestionado por TTL).
       Adicionalmente _load_delta trae lo más reciente y mergea.
    4. force_refresh=True → invalida ambos cachés y fuerza carga completa.

    El filtro por municipio se aplica en memoria — no genera llamadas extra.
    """
    if force_refresh:
        _load_full.clear()
        _load_delta.clear()

    try:
        df_base, ts_base = _load_full(api_key)

        # Intentar delta para capturar registros llegados desde la última carga completa.
        # Si _load_delta también está en caché, no hay llamada a Bubble.
        df_delta, ts_delta = _load_delta(api_key, ts_base)

        if not df_delta.empty:
            df    = _merge_delta(df_base, df_delta)
            ts_ok = ts_delta
        else:
            df    = df_base
            ts_ok = ts_base

    except Exception as e:
        logger.warning("Error cargando desde Bubble: %s. Devolviendo DataFrame vacío.", e)
        return (
            pd.DataFrame(columns=list(FIELD_MAP.values()) + [
                "duracion_min", "fecha", "encuestador_id", "terminada",
            ]),
            None,
        )

    if municipios:
        munis_upper = [m.strip().upper() for m in municipios]
        df = df[df["municipio"].isin(munis_upper)].copy()

    return df, _ts_to_dt(ts_ok)


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ── Script de prueba (ejecutar desde terminal) ─────────────────────────────────
if __name__ == "__main__":
    import os
    import types

    API_KEY = os.getenv("BUBBLE_API_KEY", "3e40b6cbea8e733fe3e6ac89f1f796b5")

    # Mock mínimo de st.cache_data para correr fuera de Streamlit
    _store: dict = {}

    def _mock_cache(ttl=None, show_spinner=True):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                key = repr(args) + repr(sorted(kwargs.items()))
                if key not in _store:
                    _store[key] = fn(*args, **kwargs)
                return _store[key]
            wrapper.clear = _store.clear
            wrapper.__wrapped__ = fn
            return wrapper
        return decorator

    import bubble_connector as bc
    bc.st = types.SimpleNamespace(cache_data=_mock_cache)
    bc._load_full  = _mock_cache()(bc._load_full.__wrapped__)
    bc._load_delta = _mock_cache()(bc._load_delta.__wrapped__)

    print("── Carga completa ───────────────────────────────")
    df, ts = bc.get_encuestas(API_KEY)
    total      = len(df)
    terminadas = int(df["terminada"].sum()) if total else 0
    print(f"Registros     : {total}")
    print(f"Terminadas    : {terminadas} ({terminadas/total*100:.1f}%)" if total else "Sin registros")
    print(f"Última act.   : {ts}")
    print(f"Municipios    : {sorted(df['municipio'].dropna().unique().tolist())}")

    print("\n── Delta simulado (desde hace 30 min) ───────────")
    df_d, _ = bc._load_delta(API_KEY, time.time() - 1800)
    print(f"Registros delta: {len(df_d)}")

    print("\n✅ Prueba completada.")