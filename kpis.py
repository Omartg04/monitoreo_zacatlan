"""
CEOP · kpis.py — Zacatlán
Cálculo de KPIs de avance: meta global, meta por sección electoral,
desagregación por encuestador/equipo y cobertura de cuotas demográficas.

Todos los cálculos asumen que `df` ya pasó por bubble_connector._transform()
y por _transform_zacatlan() de este mismo proyecto (ver transform_zacatlan.py),
es decir, que existen al menos las columnas:
    folio, seccion_electoral, encuestador_id, encuestador_nombre, equipo,
    terminada, edad, sexo, fecha_creacion, duracion_min

Uso típico (Streamlit):
    from kpis import resumen_global, avance_por_seccion, avance_por_encuestador, avance_cuotas
"""
from __future__ import annotations

import pandas as pd

from config import (
    META_GLOBAL, META_SUBMODULO, METAS_POR_SECCION,
    SECCIONES_POR_EQUIPO, SECCIONES_FUERA_MUESTRA,
)

# ── Buckets de edad — DEBEN coincidir con las llaves de cuotas en METAS_POR_SECCION ──
EDAD_BUCKETS = [
    (18, 29, "18-29"),
    (30, 44, "30-44"),
    (45, 59, "45-59"),
    (60, 200, "60+"),
]


def bin_edad_cuota(edad) -> str | None:
    """Mapea una edad numérica al bucket de cuota correspondiente (18-29/30-44/45-59/60+)."""
    if pd.isna(edad):
        return None
    edad = int(edad)
    for lo, hi, label in EDAD_BUCKETS:
        if lo <= edad <= hi:
            return label
    return None  # edad fuera de rango (<18) — revisar dato


def bin_sexo_cuota(sexo: str | None) -> str | None:
    """Normaliza 'sexo' a 'H'/'M' para cruzar contra cuotas. Ajustar valores según catálogo Bubble."""
    if not sexo:
        return None
    s = str(sexo).strip().upper()
    if s in ("H", "HOMBRE", "MASCULINO", "M_HOMBRE"):
        return "H"
    if s in ("M", "MUJER", "FEMENINO"):
        return "M"
    return None


# ── KPI 1: Meta global vs avance ──────────────────────────────────────────────

def resumen_global(df: pd.DataFrame) -> dict:
    """
    Meta global = suma de meta_encuestas de todas las secciones (830).
    Avance = encuestas terminadas en el universo de secciones con meta
    (se excluyen SECCIONES_FUERA_MUESTRA por si aparecen registros ahí).
    """
    df_universo = df[~df["seccion_electoral"].isin(SECCIONES_FUERA_MUESTRA)]

    terminadas = int(df_universo["terminada"].sum())
    levantadas = len(df_universo)

    return {
        "meta_global":       META_GLOBAL,
        "levantadas":        levantadas,
        "terminadas":        terminadas,
        "avance_pct":        round(100 * terminadas / META_GLOBAL, 1) if META_GLOBAL else 0.0,
        "faltan":            max(META_GLOBAL - terminadas, 0),
        "meta_submodulo_A":  META_SUBMODULO["A"],
        "meta_submodulo_B":  META_SUBMODULO["B"],
    }


# ── KPI 2: Secciones cubiertas (meta vs avance por sección electoral) ──────────

def avance_por_seccion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Una fila por sección electoral con meta, avance, % y semáforo de cobertura.
    Incluye TODAS las secciones de METAS_POR_SECCION, incluso con avance=0.
    """
    terminadas = (
        df[df["terminada"]]
        .groupby("seccion_electoral")
        .size()
        .rename("avance")
    )

    filas = []
    for seccion, meta_info in METAS_POR_SECCION.items():
        avance = int(terminadas.get(seccion, 0))
        meta = meta_info["meta_encuestas"]
        pct = round(100 * avance / meta, 1) if meta else 0.0
        filas.append({
            "seccion":     seccion,
            "localidad":   meta_info["localidad"],
            "tipo":        meta_info["tipo"],
            "submodulo":   meta_info["submodulo"],
            "equipo":      meta_info["equipo"],
            "meta":        meta,
            "avance":      avance,
            "pct":         pct,
            "cubierta":    avance >= meta,
            "semaforo":    _semaforo_avance(pct),
        })

    return pd.DataFrame(filas).sort_values("seccion").reset_index(drop=True)


def _semaforo_avance(pct: float) -> str:
    """Semáforo simple de avance por sección. Ajustar cortes según criterio del cliente."""
    if pct >= 100:
        return "verde"
    if pct >= 60:
        return "amarillo"
    return "rojo"


# ── KPI 3: Desagregación por encuestador / equipo ─────────────────────────────

def avance_por_encuestador(df: pd.DataFrame, seccion: int | None = None) -> pd.DataFrame:
    """
    Avance por encuestador (folios totales y terminados, duración promedio).
    Si se pasa `seccion`, filtra primero a esa sección electoral.
    """
    d = df if seccion is None else df[df["seccion_electoral"] == seccion]

    g = d.groupby(["encuestador_id", "encuestador_nombre"], dropna=False)
    out = g.agg(
        levantadas=("folio", "count"),
        terminadas=("terminada", "sum"),
        duracion_prom_min=("duracion_min", "mean"),
        secciones_trabajadas=("seccion_electoral", "nunique"),
    ).reset_index()

    out["duracion_prom_min"] = out["duracion_prom_min"].round(1)
    out["terminadas"] = out["terminadas"].astype(int)
    return out.sort_values("levantadas", ascending=False).reset_index(drop=True)


def avance_por_equipo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Avance agregado por equipo de campo (según asignación de secciones en
    METAS_POR_SECCION / SECCIONES_POR_EQUIPO). Un equipo puede cubrir varias
    secciones; se suma meta y avance de todas las que tiene asignadas.
    """
    av_sec = avance_por_seccion(df).set_index("seccion")

    filas = []
    for equipo, secciones in SECCIONES_POR_EQUIPO.items():
        meta_total   = sum(METAS_POR_SECCION[s]["meta_encuestas"] for s in secciones)
        avance_total = int(av_sec.loc[secciones, "avance"].sum())
        pct = round(100 * avance_total / meta_total, 1) if meta_total else 0.0
        filas.append({
            "equipo":          equipo,
            "n_secciones":     len(secciones),
            "secciones":       secciones,
            "meta":            meta_total,
            "avance":          avance_total,
            "pct":             pct,
            "semaforo":        _semaforo_avance(pct),
        })

    return pd.DataFrame(filas).sort_values("pct").reset_index(drop=True)


# ── KPI 4: Cobertura de cuotas demográficas por sección ───────────────────────

def avance_cuotas(df: pd.DataFrame, seccion: int) -> pd.DataFrame:
    """
    Para una sección dada: meta vs avance por celda sexo×rango_edad.
    Devuelve una fila por celda (8 filas: 4 rangos × H/M).
    """
    meta_info = METAS_POR_SECCION[seccion]
    d = df[(df["seccion_electoral"] == seccion) & (df["terminada"])]

    d = d.assign(
        _sexo_q=d["sexo"].apply(bin_sexo_cuota),
        _edad_q=d["edad"].apply(bin_edad_cuota),
    )
    conteo = d.groupby(["_edad_q", "_sexo_q"]).size()

    filas = []
    for rango, cuotas in meta_info["cuotas"].items():
        for sexo, meta in cuotas.items():
            avance = int(conteo.get((rango, sexo), 0))
            pct = round(100 * avance / meta, 1) if meta else 0.0
            filas.append({
                "seccion": seccion,
                "rango_edad": rango,
                "sexo": sexo,
                "meta": meta,
                "avance": avance,
                "pct": pct,
                "semaforo": _semaforo_avance(pct),
            })

    return pd.DataFrame(filas)


def avance_cuotas_global(df: pd.DataFrame) -> pd.DataFrame:
    """
    Suma de cuotas (meta y avance) de TODAS las secciones, por celda sexo×edad.
    Útil para detectar sesgo agregado (p.ej. sobre-representación de 60+ H).
    """
    d = df[df["terminada"]].copy()
    d["_sexo_q"] = d["sexo"].apply(bin_sexo_cuota)
    d["_edad_q"] = d["edad"].apply(bin_edad_cuota)
    conteo = d.groupby(["_edad_q", "_sexo_q"]).size()

    meta_acum: dict[tuple[str, str], int] = {}
    for meta_info in METAS_POR_SECCION.values():
        for rango, cuotas in meta_info["cuotas"].items():
            for sexo, meta in cuotas.items():
                meta_acum[(rango, sexo)] = meta_acum.get((rango, sexo), 0) + meta

    filas = []
    for (rango, sexo), meta in meta_acum.items():
        avance = int(conteo.get((rango, sexo), 0))
        pct = round(100 * avance / meta, 1) if meta else 0.0
        filas.append({
            "rango_edad": rango, "sexo": sexo,
            "meta": meta, "avance": avance, "pct": pct,
            "semaforo": _semaforo_avance(pct),
        })

    return pd.DataFrame(filas).sort_values(["rango_edad", "sexo"]).reset_index(drop=True)
