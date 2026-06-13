"""
CEOP · flags.py — Zacatlán
Sistema de flags de calidad y sesgo. Cada flag_* recibe el DataFrame ya
transformado (ver transform_zacatlan.py) y devuelve el mismo DataFrame con
columnas adicionales `flag_<nombre>` (bool) y `flag_<nombre>_nivel`
('rojo' | 'amarillo' | None).

Reglas implementadas (ver Objetivo del Proyecto):
  1. flag_duracion              — tiempos de entrevista anómalos
  2. flag_straightlining        — patrones de respuesta sospechosos
  3. flag_georef_fuera_zona     — georreferenciación fuera de zona
  4. flag_horario_atipico       — horarios de levantamiento atípicos
  5. flag_inconsistencia_conocimiento — Bloque 6 vs Bloque 7 por candidato
  6. resumen_cobertura_desbalanceada — cobertura geográfica desbalanceada
     (a nivel sección — usa kpis.avance_por_seccion)

Varios umbrales son PROPUESTAS marcadas con TODO — confirmar con stakeholder
antes de usar en producción (ver también config.py).
"""
from __future__ import annotations

import json
import re

import pandas as pd
from shapely.geometry import Point, shape

from config import (
    DUR_MIN_MIN, DUR_MAX_MIN,
    UMBRAL_STRAIGHTLINING_BLOQUE7, UMBRAL_STRAIGHTLINING_BLOQUE6,
    BATERIAS_STRAIGHTLINING, GEOJSON_SECCIONES, CLAVE_MUNICIPIO,
    HORA_INICIO_OPERATIVO, HORA_FIN_OPERATIVO,
    CANDIDATOS, ATRIBUTOS_BLOQUE7,
)
import kpis


# ── 1. Duración de entrevista ─────────────────────────────────────────────────


def flag_duracion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evalúa duración SOLO en encuestas terminadas (`terminada == True`).
    Las encuestas en progreso tienen `fecha_modificacion` aún abierta y una
    duración artificialmente corta que inflaría falsos positivos.

    Rojo:    duracion_min < DUR_MIN_MIN  o  > DUR_MAX_MIN
    Amarillo: entre DUR_MIN_MIN y DUR_MIN_MIN × 1.2 (zona de alerta temprana)
    No evaluable (flag_duracion_nivel = None): encuesta no terminada.
    """
    d = df.copy()
    dur = d["duracion_min"]
    confiable = d.get("duracion_confiable", pd.Series(True, index=d.index))
    terminada = d.get("terminada", pd.Series(False, index=d.index))

    evaluable = terminada & confiable

    muy_corta = dur < DUR_MIN_MIN
    muy_larga  = dur > DUR_MAX_MIN
    cerca_min  = dur.between(DUR_MIN_MIN, DUR_MIN_MIN * 1.2)

    rojo     = muy_corta | muy_larga
    amarillo = cerca_min & ~rojo

    d["flag_duracion"] = evaluable & (rojo | amarillo)
    d["flag_duracion_nivel"] = None
    d.loc[evaluable & amarillo, "flag_duracion_nivel"] = "amarillo"
    d.loc[evaluable & rojo,     "flag_duracion_nivel"] = "rojo"
    return d



# ── 2. Straightlining ─────────────────────────────────────────────────────────

def _es_straightline(row: pd.Series, columnas: list[str]) -> bool:
    valores = row[columnas]
    no_nulos = valores.dropna()
    if len(no_nulos) < len(columnas):
        return False  # batería incompleta — no se evalúa
    return no_nulos.nunique() == 1


def flag_straightlining(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evalúa SOLO encuestas terminadas — las incompletas tienen baterías
    parciales que _es_straightline ya filtra, pero conviene ser explícitos.

    Si TODAS las respuestas de una batería 'bloque7_*' (7 ítems) son idénticas
    → rojo. Si ocurre solo en una batería 'bloque6_*' (5 ítems) → amarillo.
    """
    d = df.copy()
    terminada = d.get("terminada", pd.Series(False, index=d.index))

    detalle = pd.DataFrame(index=d.index)
    for nombre, columnas in BATERIAS_STRAIGHTLINING.items():
        cols_existentes = [c for c in columnas if c in d.columns]
        if len(cols_existentes) != len(columnas):
            continue  # columnas todavía no disponibles en el df — saltar
        detalle[nombre] = d.apply(_es_straightline, axis=1, columnas=columnas)

    cols_b7 = [c for c in detalle.columns if c.startswith("bloque7_")]
    cols_b6 = [c for c in detalle.columns if c.startswith("bloque6_")]
    n_b7 = detalle[cols_b7].sum(axis=1) if cols_b7 else pd.Series(0, index=d.index)
    n_b6 = detalle[cols_b6].sum(axis=1) if cols_b6 else pd.Series(0, index=d.index)

    d["flag_straightlining_detalle"] = detalle.apply(
        lambda r: [c for c in detalle.columns if r[c]], axis=1
    ) if not detalle.empty else [[] for _ in range(len(d))]
    d["flag_straightlining_n_baterias"] = n_b7 + n_b6

    rojo     = terminada & (n_b7 >= 1)
    amarillo = terminada & (~rojo) & (n_b6 >= 1)

    d["flag_straightlining"] = rojo | amarillo
    d["flag_straightlining_nivel"] = None
    d.loc[amarillo, "flag_straightlining_nivel"] = "amarillo"
    d.loc[rojo,     "flag_straightlining_nivel"] = "rojo"
    return d


# ── 3. Georreferenciación fuera de zona ────────────────────────────────────────

_POLIGONOS_CACHE: dict[int, object] | None = None


def _cargar_poligonos(path: str = GEOJSON_SECCIONES) -> dict[int, object]:
    global _POLIGONOS_CACHE
    if _POLIGONOS_CACHE is not None:
        return _POLIGONOS_CACHE

    with open(path, encoding="utf-8") as f:
        gj = json.load(f)

    poligonos: dict[int, object] = {}
    for feat in gj["features"]:
        seccion = feat["properties"]["seccion"]
        poligonos[seccion] = shape(feat["geometry"])

    _POLIGONOS_CACHE = poligonos
    return poligonos


def _ubicar_punto(lat, lon, poligonos: dict[int, object]) -> int | None:
    """Devuelve el número de sección cuyo polígono contiene (lat, lon), o None
    si el punto no cae en ninguna sección del GEOJSON (municipio 208)."""
    if pd.isna(lat) or pd.isna(lon):
        return None
    pt = Point(lon, lat)  # shapely usa (x=lon, y=lat)
    for seccion, geom in poligonos.items():
        if geom.contains(pt):
            return seccion
    return None


def flag_georef_fuera_zona(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compara la sección electoral DECLARADA (seccion_electoral, capturada por
    el encuestador) contra la sección cuyo polígono CONTIENE las coordenadas
    (latitud/longitud) reportadas por google_address.

    Niveles:
      - Sin lat/lon                              → flag_georef_nivel = None (no evaluable)
      - Punto cae en la sección declarada        → sin flag
      - Punto cae en OTRA sección de Zacatlán    → amarillo (posible error de
        captura de sección o entrevista en colindancia)
      - Punto NO cae en ninguna sección de
        Zacatlán (municipio 208)                 → rojo (fuera de zona operativa)
    """
    d = df.copy()
    poligonos = _cargar_poligonos()

    d["seccion_georef"] = d.apply(
        lambda r: _ubicar_punto(r.get("latitud"), r.get("longitud"), poligonos), axis=1
    )

    tiene_coords = d["latitud"].notna() & d["longitud"].notna()
    fuera_municipio = tiene_coords & d["seccion_georef"].isna()
    otra_seccion = (
        tiene_coords
        & d["seccion_georef"].notna()
        & (d["seccion_georef"] != d["seccion_electoral"])
    )

    d["flag_georef"] = fuera_municipio | otra_seccion
    d["flag_georef_nivel"] = None
    d.loc[otra_seccion, "flag_georef_nivel"] = "amarillo"
    d.loc[fuera_municipio, "flag_georef_nivel"] = "rojo"
    return d


# ── 4. Horario de levantamiento atípico ────────────────────────────────────────

def flag_horario_atipico(df: pd.DataFrame) -> pd.DataFrame:
    """
    Amarillo: entrevista iniciada fuera del horario operativo declarado
    (HORA_INICIO_OPERATIVO–HORA_FIN_OPERATIVO, hora local Ciudad de México).
    Usa `fecha_creacion` (debe ser tz-aware UTC; ver transform_zacatlan).
    """
    d = df.copy()
    hora_local = d["fecha_creacion"].dt.tz_convert("America/Mexico_City").dt.hour

    fuera_horario = ~hora_local.between(HORA_INICIO_OPERATIVO, HORA_FIN_OPERATIVO - 1)

    d["flag_horario"] = fuera_horario
    d["flag_horario_nivel"] = None
    d.loc[fuera_horario, "flag_horario_nivel"] = "amarillo"
    return d


# ── 5. Inconsistencia: "no conoce al candidato" pero opina sobre sus atributos ─

# TODO: confirmar contra catálogo real de respuestas de Bubble. Patrones
# laxos basados en los nombres de variable del diccionario (..._texto).
_PATRON_NO_CONOCE = re.compile(r"no\s*(?:lo|la)?\s*conoc", re.IGNORECASE)
_PATRON_NO_SABE   = re.compile(r"no\s*sabe|no\s*contesta|n\/?d", re.IGNORECASE)


def flag_inconsistencia_conocimiento(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evalúa SOLO encuestas terminadas — en incompletas Bloque 7 puede estar
    vacío aunque Bloque 6 ya tenga respuesta, generando falsos positivos.

    Para cada candidato: si conocimiento_<cand> indica "no lo conoce" pero
    el entrevistado SÍ emitió opiniones sustantivas en >=1 atributo del Bloque 7
    → inconsistencia. Amarillo si ocurre con 1 candidato, rojo si ocurre con 2+.
    """
    d = df.copy()
    terminada = d.get("terminada", pd.Series(False, index=d.index))
    n_incons = pd.Series(0, index=d.index)
    detalle: list[list[str]] = [[] for _ in range(len(d))]

    for cand in CANDIDATOS:
        col_conoce = f"conocimiento_{cand}"
        if col_conoce not in d.columns:
            continue

        no_conoce = d[col_conoce].astype(str).str.contains(_PATRON_NO_CONOCE, na=False)

        cols_atrib = [f"{atrib}_{cand}" for atrib in ATRIBUTOS_BLOQUE7 if f"{atrib}_{cand}" in d.columns]
        if not cols_atrib:
            continue

        opina_sustantivo = pd.DataFrame({
            c: d[c].notna() & ~d[c].astype(str).str.contains(_PATRON_NO_SABE, na=False)
            for c in cols_atrib
        }).any(axis=1)

        incons_cand = terminada & no_conoce & opina_sustantivo
        n_incons += incons_cand.astype(int)
        for i, flagged in enumerate(incons_cand):
            if flagged:
                detalle[i].append(cand)

    d["flag_inconsistencia_conocimiento_detalle"] = detalle
    d["flag_inconsistencia_conocimiento_n"] = n_incons
    d["flag_inconsistencia_conocimiento"] = n_incons > 0
    d["flag_inconsistencia_conocimiento_nivel"] = None
    d.loc[n_incons == 1, "flag_inconsistencia_conocimiento_nivel"] = "amarillo"
    d.loc[n_incons >= 2, "flag_inconsistencia_conocimiento_nivel"] = "rojo"
    return d


# ── 6. Cobertura geográfica desbalanceada (nivel sección) ──────────────────────

def resumen_cobertura_desbalanceada(df: pd.DataFrame) -> pd.DataFrame:
    """
    A partir de kpis.avance_por_seccion: marca secciones cuyo % de avance se
    desvía fuertemente del avance promedio de su mismo equipo.

    rojo:     pct == 0  y al menos otra sección del mismo equipo ya tiene
              avance > 0 (sugiere brigada sin desplegar / sección abandonada).
    amarillo: pct < 50% del promedio del equipo (rezago relativo).
    """
    av = kpis.avance_por_seccion(df)

    prom_equipo = av.groupby("equipo")["pct"].transform("mean")
    avance_equipo_max = av.groupby("equipo")["avance"].transform("max")

    rojo = (av["avance"] == 0) & (avance_equipo_max > 0)
    amarillo = (~rojo) & (av["pct"] < 0.5 * prom_equipo) & (prom_equipo > 0)

    av["flag_cobertura"] = rojo | amarillo
    av["flag_cobertura_nivel"] = None
    av.loc[amarillo, "flag_cobertura_nivel"] = "amarillo"
    av.loc[rojo, "flag_cobertura_nivel"] = "rojo"
    return av


# ── Orquestador ────────────────────────────────────────────────────────────────

def aplicar_todos_los_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica los flags de nivel-registro en cadena. Para cobertura por sección
    usar resumen_cobertura_desbalanceada(df) por separado (devuelve otro shape)."""
    d = flag_duracion(df)
    d = flag_straightlining(d)
    d = flag_georef_fuera_zona(d)
    d = flag_horario_atipico(d)
    d = flag_inconsistencia_conocimiento(d)

    cols_nivel = [c for c in d.columns if c.endswith("_nivel") and c.startswith("flag_")]
    d["flags_rojo_n"] = (d[cols_nivel] == "rojo").sum(axis=1)
    d["flags_amarillo_n"] = (d[cols_nivel] == "amarillo").sum(axis=1)
    return d