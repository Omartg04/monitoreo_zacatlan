"""
Zacatlán PIE – Visualizador de Monitoreo y Auditoría de Encuestas
Zacatlán, Puebla · Encuesta L2 · 2026
Ejecutar: streamlit run app.py
"""
import copy
import json
import time
from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import LoginError

from config import (
    VERDE, VERDE_L, AZUL, AZUL_L, NARANJA, ROJO, AMARILLO, GRIS_BG,
    DUR_MIN_MIN, DUR_MAX_MIN, AUTO_REFRESH_SEC,
    META_GLOBAL, META_SUBMODULO, METAS_POR_SECCION,
    EQUIPOS, SECCIONES_POR_EQUIPO, SECCIONES_FUERA_MUESTRA,
    GEOJSON_SECCIONES, ZACATLAN_CENTRO, ZACATLAN_ZOOM,
    CANDIDATOS, ATRIBUTOS_BLOQUE7, ROLES,
)
import kpis
import flags
from transform_zacatlan import get_encuestas
from bubble_connector import normalizar_nombre

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Zacatlán PIE 2026",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
html, body, [class*="css"] {{ font-family: 'IBM Plex Sans', sans-serif; background: {GRIS_BG}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}

.zac-header {{
    background: linear-gradient(120deg, {AZUL} 0%, {AZUL_L} 60%, {VERDE} 100%);
    color: white; padding: 16px 26px; border-radius: 10px;
    display: flex; align-items: center; gap: 18px; margin-bottom: 1.1rem;
}}
.zac-header h1 {{ margin: 0; font-size: 1.5rem; font-weight: 700; line-height: 1.2; }}
.zac-header p  {{ margin: 2px 0 0; font-size: 0.82rem; opacity: 0.82; }}

.kpi-card {{
    background: white; border-radius: 9px; padding: 14px 18px;
    border-left: 5px solid {VERDE}; box-shadow: 0 2px 6px rgba(0,0,0,.07);
    height: 100%;
}}
.kpi-val   {{ font-size: 2rem; font-weight: 700; color: {VERDE};
              font-family: 'IBM Plex Mono', monospace; line-height: 1; }}
.kpi-label {{ font-size: 0.73rem; color: #555; text-transform: uppercase;
              letter-spacing:.05em; margin-top:4px; }}
.kpi-sub   {{ font-size: 0.78rem; color: #888; margin-top: 3px; }}
.kpi-card.azul    {{ border-left-color: {AZUL_L}; }}
.kpi-card.azul .kpi-val {{ color: {AZUL_L}; }}
.kpi-card.naranja {{ border-left-color: {NARANJA}; }}
.kpi-card.naranja .kpi-val {{ color: {NARANJA}; }}
.kpi-card.rojo    {{ border-left-color: {ROJO}; }}
.kpi-card.rojo .kpi-val {{ color: {ROJO}; }}
.kpi-card.amarillo {{ border-left-color: {AMARILLO}; }}
.kpi-card.amarillo .kpi-val {{ color: {AMARILLO}; }}

.sec-title {{
    font-size: 1rem; font-weight: 600; color: {AZUL};
    border-bottom: 2px solid {VERDE_L}; padding-bottom: 3px; margin: 16px 0 10px;
}}
.ts-badge {{
    font-size: 0.72rem; color: #888; font-family: 'IBM Plex Mono', monospace;
    background: #eef1f5; border-radius: 4px; padding: 2px 8px; display: inline-block;
}}
section[data-testid="stSidebar"] {{ background: {AZUL}; }}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] .stMarkdown p {{ color: #B8CDE0 !important; }}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{ color: white !important; }}
</style>
""", unsafe_allow_html=True)


# ── Autenticación ──────────────────────────────────────────────────────────────
_raw_users = st.secrets.get("auth", {}).get("credentials", {}).get("usernames", {})
_credentials = {
    "usernames": {
        str(u): {
            "name":     str(data["name"]),
            "password": str(data["password"]),
        }
        for u, data in _raw_users.items()
    }
}
_cookie_name   = str(st.secrets.get("auth", {}).get("cookie_name",        "zacatlan_pie_session"))
_cookie_key    = str(st.secrets.get("auth", {}).get("cookie_key",         "zacatlan_pie_dev_key"))
_cookie_expiry = int(st.secrets.get("auth", {}).get("cookie_expiry_days", 1))

authenticator = stauth.Authenticate(_credentials, _cookie_name, _cookie_key, _cookie_expiry)

try:
    authenticator.login(location="main", key="zacatlan_pie_login")
except LoginError as e:
    st.error(str(e))
    st.stop()

if not st.session_state.get("authentication_status"):
    if st.session_state.get("authentication_status") is False:
        st.error("Usuario o contraseña incorrectos.")
    else:
        st.info("Ingresa tus credenciales para acceder a Zacatlán PIE.")
    st.stop()

_username   = st.session_state["username"]
_rol_cfg    = ROLES.get(_username, {"rol": "equipo", "equipos": [], "secciones": []})
_rol        = _rol_cfg.get("rol", "equipo")
_secs_permitidas = _rol_cfg.get("secciones", [])

with st.sidebar:
    authenticator.logout(button_name="🔒 Cerrar sesión", location="sidebar", key="zacatlan_pie_logout")
    st.markdown(f"**{st.session_state.get('name', _username)}**")
    st.caption("Coordinación estatal" if _rol == "estatal" else f"Equipo: {', '.join(_rol_cfg.get('equipos', []))}")
    st.markdown("---")


# ── Auto-refresh ───────────────────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()

if time.time() - st.session_state["last_refresh"] > AUTO_REFRESH_SEC:
    st.session_state["last_refresh"] = time.time()
    st.rerun()


# ── Carga de datos ─────────────────────────────────────────────────────────────
API_KEY = st.secrets.get("BUBBLE_API_KEY", "")

_filtro_secciones = None if _rol == "estatal" else _secs_permitidas
with st.spinner("Cargando datos del operativo…"):
    df_raw, ultima_actualizacion = get_encuestas(API_KEY, secciones=_filtro_secciones)

# Aplicar flags de calidad/sesgo sobre el universo permitido al usuario
with st.spinner("Calculando flags de calidad…"):
    df_raw = flags.aplicar_todos_los_flags(df_raw) if not df_raw.empty else df_raw


@st.cache_data(ttl=AUTO_REFRESH_SEC, show_spinner=False)
def load_geojson(path_str):
    p = Path(path_str)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

GEOJSON = load_geojson(GEOJSON_SECCIONES)


# ── Helpers ────────────────────────────────────────────────────────────────────
def kpi(col, val, label, sub="", cls=""):
    col.markdown(f"""
    <div class="kpi-card {cls}">
      <div class="kpi-val">{val}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


def color_semaforo(val):
    if val == "verde":    return "background-color:#D4EDDA;color:#155724;font-weight:700"
    if val == "amarillo": return "background-color:#FFF3CD;color:#856404;font-weight:700"
    if val == "rojo":     return "background-color:#F8D7DA;color:#721C24;font-weight:700"
    return ""


def color_pct(val):
    if pd.isna(val): return ""
    if val >= 100: return "background-color:#D4EDDA;color:#155724;font-weight:700"
    if val >= 60:  return "background-color:#FFF3CD;color:#856404;font-weight:700"
    return               "background-color:#F8D7DA;color:#721C24;font-weight:700"


def color_dur(val):
    if pd.isna(val): return ""
    if DUR_MIN_MIN <= val <= DUR_MAX_MIN: return "background-color:#D4EDDA;color:#155724;font-weight:600"
    if val < DUR_MIN_MIN:                 return "background-color:#F8D7DA;color:#721C24;font-weight:600"
    return                                       "background-color:#FFF3CD;color:#856404;font-weight:600"


def pct_bar(df_in, campo, titulo, orden=None, colors=None, height=260):
    if campo not in df_in.columns or df_in[campo].dropna().empty:
        return None
    cnt = df_in[campo].value_counts(normalize=True).mul(100).round(1).reset_index()
    cnt.columns = ["Respuesta", "Porcentaje"]
    if orden:
        cnt["Respuesta"] = pd.Categorical(cnt["Respuesta"], categories=orden, ordered=True)
        cnt = cnt.sort_values("Respuesta")
    else:
        cnt = cnt.sort_values("Porcentaje", ascending=True)
    cs = colors or [VERDE_L, VERDE, AZUL_L, NARANJA, ROJO, AMARILLO, "#aaa"]
    fig = px.bar(cnt, x="Porcentaje", y="Respuesta", orientation="h",
                 color="Respuesta", color_discrete_sequence=cs,
                 text=cnt["Porcentaje"].apply(lambda x: f"{x}%"),
                 title=titulo, height=height)
    fig.update_traces(textposition="outside")
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      showlegend=False, font_family="IBM Plex Sans",
                      margin=dict(t=45, b=5, l=220), xaxis_range=[0, 105])
    return fig


def show_chart(fig, **kwargs):
    if fig:
        st.plotly_chart(fig, use_container_width=True, **kwargs)
    else:
        st.info("Sin datos suficientes para esta gráfica.")


# ── Sidebar — filtros ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Filtros")
    st.markdown("---")

    # Equipo (solo rol estatal puede ver/elegir todos)
    if _rol == "estatal":
        equipo_opts = ["Todos los equipos"] + EQUIPOS
        equipo_sel = st.selectbox("Equipo", equipo_opts)
    else:
        equipo_sel = _rol_cfg.get("equipos", ["Sin asignar"])[0]
        st.markdown(f"**Equipo:** {equipo_sel}")

    # Sección electoral
    if equipo_sel == "Todos los equipos":
        secciones_disp = sorted(METAS_POR_SECCION.keys())
    else:
        secciones_disp = sorted(SECCIONES_POR_EQUIPO.get(equipo_sel, []))

    sec_opts = ["Todas"] + secciones_disp
    sec_sel = st.selectbox(
        "Sección electoral", sec_opts,
        format_func=lambda s: "Todas" if s == "Todas"
        else f"{s} — {METAS_POR_SECCION.get(s, {}).get('localidad', '')}"
    )

    # Fecha de levantamiento
    if not df_raw.empty and "fecha" in df_raw.columns:
        fechas_disp = sorted(df_raw["fecha"].dropna().unique().tolist())
    else:
        fechas_disp = []
    fecha_sel = st.multiselect(
        "Fecha de levantamiento", fechas_disp, default=fechas_disp,
        format_func=lambda d: d.strftime("%a %d-%b") if hasattr(d, "strftime") else str(d),
    )

    st.markdown("---")

    # Encuestador
    if not df_raw.empty:
        enc_opts = ["Todos"] + sorted(df_raw["encuestador_nombre"].dropna().unique().tolist())
    else:
        enc_opts = ["Todos"]
    enc_sel = st.selectbox("Encuestador", enc_opts)

    st.markdown("---")

    if st.button("🔄 Actualizar datos", use_container_width=True):
        get_encuestas(API_KEY, secciones=_filtro_secciones, force_refresh=True)
        st.session_state["last_refresh"] = time.time()
        st.rerun()

    if ultima_actualizacion:
        ts_local = ultima_actualizacion.astimezone().strftime("%H:%M:%S")
        st.markdown(f'<div class="ts-badge">⏱ Actualizado: {ts_local}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Zacatlán PIE** · L2 · 2026")


# ── Aplicar filtros ────────────────────────────────────────────────────────────
df = df_raw.copy()

if equipo_sel != "Todos los equipos":
    df = df[df["equipo"] == equipo_sel]

if sec_sel != "Todas":
    df = df[df["seccion_electoral"] == sec_sel]

if fecha_sel and "fecha" in df.columns:
    df = df[df["fecha"].isin(fecha_sel)]

if enc_sel != "Todos":
    df = df[df["encuestador_nombre"] == enc_sel]


# ── Header ─────────────────────────────────────────────────────────────────────
titulo_geo = "Zacatlán, Puebla" if equipo_sel == "Todos los equipos" else f"Equipo {equipo_sel}"
if sec_sel != "Todas":
    titulo_geo += f" — Sección {sec_sel}"

st.markdown(f"""
<div class="zac-header">
  <div style="font-size:2.2rem">📋</div>
  <div>
    <h1>Monitoreo y Auditoría de Encuestas — {titulo_geo}</h1>
    <p>Data &amp; AI Inclusion Technologies · L2 Zacatlán · {len(df):,} registros en vista actual</p>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Tabs ───────────────────────────────────────────────────────────────────────
if _rol == "estatal":
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈  Avance vs Meta",
        "🗺️  Mapa de Cobertura",
        "🚩  Flags de Calidad y Sesgo",
        "📊  Resultados del Instrumento",
    ])
else:
    tab1, tab2, tab3 = st.tabs([
        "📈  Avance vs Meta",
        "🗺️  Mapa de Cobertura",
        "🚩  Flags de Calidad y Sesgo",
    ])
    tab4 = None


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AVANCE VS META
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if df_raw.empty:
        st.info("Sin datos disponibles todavía — verifica la conexión a Bubble (config.BUBBLE_ENDPOINT).")
    else:
        # ── KPIs globales ──────────────────────────────────────────────────────
        resumen = kpis.resumen_global(df_raw if equipo_sel == "Todos los equipos" and sec_sel == "Todas"
                                       else df)
        meta_vista = (
            META_GLOBAL if equipo_sel == "Todos los equipos" and sec_sel == "Todas"
            else (METAS_POR_SECCION[sec_sel]["meta_encuestas"] if sec_sel != "Todas"
                  else sum(METAS_POR_SECCION[s]["meta_encuestas"] for s in SECCIONES_POR_EQUIPO.get(equipo_sel, [])))
        )
        terminadas_vista = int(df["terminada"].sum())
        avance_pct_vista = round(100 * terminadas_vista / meta_vista, 1) if meta_vista else 0.0

        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        kpi(r1c1, f"{len(df):,}", "Encuestas levantadas", "en la vista actual")
        kpi(r1c2, f"{terminadas_vista:,}", "Encuestas terminadas",
            f"{round(100*terminadas_vista/max(len(df),1),1)}% del total levantado", "azul")
        kpi(r1c3, f"{meta_vista:,}", "Meta (vista actual)",
            f"Global Zacatlán: {META_GLOBAL:,}  ·  A:{META_SUBMODULO['A']} / B:{META_SUBMODULO['B']}", "naranja")
        kpi(r1c4, f"{avance_pct_vista}%", "Avance vs meta",
            f"faltan {max(meta_vista - terminadas_vista, 0):,}",
            "rojo" if avance_pct_vista < 60 else ("amarillo" if avance_pct_vista < 100 else ""))

        df_conf = df[df["duracion_confiable"]] if "duracion_confiable" in df.columns else df
        prom_t = round(df_conf["duracion_min"].mean(), 1) if len(df_conf) else 0
        st.caption(f"Duración promedio de entrevista: **{prom_t}'** (rango esperado {DUR_MIN_MIN}–{DUR_MAX_MIN} min)")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Secciones cubiertas (meta vs avance) ──────────────────────────────
        st.markdown('<div class="sec-title">Secciones cubiertas — meta vs avance</div>', unsafe_allow_html=True)

        av_sec = kpis.avance_por_seccion(df)
        if equipo_sel != "Todos los equipos":
            av_sec = av_sec[av_sec["equipo"] == equipo_sel]
        if sec_sel != "Todas":
            av_sec = av_sec[av_sec["seccion"] == sec_sel]

        n_cubiertas = int(av_sec["cubierta"].sum())
        st.caption(f"{n_cubiertas} de {len(av_sec)} secciones en vista alcanzaron su meta.")

        tbl_sec = av_sec[["seccion", "localidad", "tipo", "submodulo", "equipo", "meta", "avance", "pct", "semaforo"]].copy()
        tbl_sec.columns = ["Sección", "Localidad", "Tipo", "Submódulo", "Equipo", "Meta", "Avance", "% Avance", "Semáforo"]
        tbl_sec_styled = (
            tbl_sec.style
            .map(color_pct, subset=["% Avance"])
            .map(color_semaforo, subset=["Semáforo"])
            .format({"% Avance": "{:.1f}%"})
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"})
        )
        st.dataframe(tbl_sec_styled, use_container_width=True, hide_index=True,
                     height=min(80 + len(tbl_sec) * 35, 560))
        st.caption("🟢 ≥100% de meta  ·  🟡 60–99%  ·  🔴 <60%")

        # ── Avance por equipo ──────────────────────────────────────────────────
        if equipo_sel == "Todos los equipos":
            st.markdown('<div class="sec-title">Avance por equipo</div>', unsafe_allow_html=True)
            av_eq = kpis.avance_por_equipo(df)
            tbl_eq = av_eq[["equipo", "n_secciones", "meta", "avance", "pct", "semaforo"]].copy()
            tbl_eq.columns = ["Equipo", "N° secciones", "Meta", "Avance", "% Avance", "Semáforo"]
            st.dataframe(
                tbl_eq.style
                .map(color_pct, subset=["% Avance"])
                .map(color_semaforo, subset=["Semáforo"])
                .format({"% Avance": "{:.1f}%"})
                .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
                use_container_width=True, hide_index=True,
            )

        # ── Avance por encuestador ─────────────────────────────────────────────
        st.markdown('<div class="sec-title">Avance por encuestador</div>', unsafe_allow_html=True)
        av_enc = kpis.avance_por_encuestador(df)
        tbl_enc = av_enc[["encuestador_nombre", "levantadas", "terminadas", "duracion_prom_min", "secciones_trabajadas"]].copy()
        tbl_enc.columns = ["Encuestador", "Levantadas", "Terminadas", "Dur. prom (min)", "Secciones"]
        st.dataframe(
            tbl_enc.style
            .map(color_dur, subset=["Dur. prom (min)"])
            .format({"Dur. prom (min)": "{:.1f}"})
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
            use_container_width=True, hide_index=True,
            height=min(80 + len(tbl_enc) * 35, 420),
        )

        with st.expander("📊 Distribución de duraciones (registros confiables)", expanded=False):
            fig_box = px.box(
                df_conf, y="duracion_min", color_discrete_sequence=[VERDE],
                labels={"duracion_min": "Minutos"}, title="Duración de entrevistas",
            )
            fig_box.add_hline(y=DUR_MAX_MIN, line_dash="dash", line_color=AMARILLO,
                              annotation_text=f"Máx ({DUR_MAX_MIN} min)")
            fig_box.add_hline(y=DUR_MIN_MIN, line_dash="dot", line_color=ROJO,
                              annotation_text=f"Mín ({DUR_MIN_MIN} min)")
            fig_box.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   font_family="IBM Plex Sans", margin=dict(t=50, b=10))
            st.plotly_chart(fig_box, use_container_width=True)

        # ── Cuotas demográficas ─────────────────────────────────────────────────
        st.markdown('<div class="sec-title">Cobertura de cuotas (sexo × rango de edad)</div>', unsafe_allow_html=True)
        if sec_sel != "Todas":
            cq = kpis.avance_cuotas(df, sec_sel)
        else:
            cq = kpis.avance_cuotas_global(df)
        cq_disp = cq.copy()
        cq_disp.columns = [c.replace("_", " ").title() for c in cq_disp.columns]
        st.dataframe(
            cq_disp.style
            .map(color_pct, subset=["Pct"])
            .map(color_semaforo, subset=["Semaforo"])
            .format({"Pct": "{:.1f}%"})
            .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
            use_container_width=True, hide_index=True,
        )
        st.caption("Avance de cuotas por sexo (H/M) y rango de edad respecto a la meta definida en la Guía de Coordinadores.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MAPA DE COBERTURA
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="sec-title">Mapa de cobertura por sección electoral</div>', unsafe_allow_html=True)

    if GEOJSON is None:
        st.warning(f"No se encontró {GEOJSON_SECCIONES}. Colócalo junto a app.py.")
    else:
        av_sec_all = kpis.avance_por_seccion(df)
        av_lookup = av_sec_all.set_index("seccion").to_dict(orient="index")

        mapa = folium.Map(location=ZACATLAN_CENTRO, zoom_start=ZACATLAN_ZOOM, tiles="CartoDB positron")

        geojson_enriq = copy.deepcopy(GEOJSON)
        for feature in geojson_enriq["features"]:
            sec = feature["properties"].get("seccion")
            info = av_lookup.get(sec)
            if info is None:
                feature["properties"].update({
                    "meta": 0, "avance": 0, "pct": 0.0,
                    "equipo": "—", "localidad": "—",
                    "estado": "Fuera de muestra",
                })
            else:
                feature["properties"].update({
                    "meta":      int(info["meta"]),
                    "avance":    int(info["avance"]),
                    "pct":       float(info["pct"]),
                    "equipo":    info["equipo"],
                    "localidad": info["localidad"],
                    "estado":    "🟢 En meta" if info["pct"] >= 100 else
                                 ("🟡 En riesgo" if info["pct"] >= 60 else "🔴 Bajo meta"),
                })

        def style_sec(feature):
            props = feature["properties"]
            if props.get("estado") == "Fuera de muestra":
                return {"fillColor": "#CCCCCC", "color": "#999999", "weight": 0.6, "fillOpacity": 0.35}
            pct = props.get("pct", 0)
            if pct >= 100:
                return {"fillColor": VERDE,    "color": "#1A5C42", "weight": 1.4, "fillOpacity": 0.78}
            if pct >= 60:
                return {"fillColor": AMARILLO, "color": "#8a6200", "weight": 1.4, "fillOpacity": 0.78}
            return     {"fillColor": ROJO,     "color": "#7b1a14", "weight": 1.4, "fillOpacity": 0.78}

        tooltip_html = folium.GeoJsonTooltip(
            fields=["seccion", "localidad", "equipo", "estado", "avance", "meta", "pct"],
            aliases=["Sección:", "Localidad:", "Equipo:", "Estado:", "Avance:", "Meta:", "% avance:"],
            localize=True, sticky=True, labels=True,
            style=(
                "background-color:white;border:1px solid #2E7D5E;"
                "border-radius:6px;padding:8px 12px;"
                "font-family:'IBM Plex Sans',sans-serif;font-size:13px;"
                "box-shadow:0 2px 8px rgba(0,0,0,0.15);"
            ),
        )

        folium.GeoJson(
            geojson_enriq, style_function=style_sec,
            highlight_function=lambda f: {"fillOpacity": 0.95, "weight": 2.5, "color": AZUL},
            tooltip=tooltip_html, name="Secciones electorales",
        ).add_to(mapa)

        # Marcadores de georreferenciación fuera de zona (flag_georef)
        if "flag_georef" in df.columns:
            df_geo = df[df["flag_georef"] & df["latitud"].notna() & df["longitud"].notna()]
            for _, r in df_geo.iterrows():
                color = "red" if r["flag_georef_nivel"] == "rojo" else "orange"
                folium.CircleMarker(
                    location=[r["latitud"], r["longitud"]], radius=5,
                    color=color, fill=True, fill_opacity=0.85,
                    popup=f"Folio {r['folio']} · sección declarada {r['seccion_electoral']} "
                          f"· sección por coordenadas {r.get('seccion_georef')}",
                ).add_to(mapa)

        folium.LayerControl().add_to(mapa)
        st_folium(mapa, width="100%", height=540, returned_objects=[])

        st.caption(
            "🟢 ≥100% de meta · 🟡 60–99% · 🔴 <60% · ⬜ Fuera de la muestra del operativo. "
            "Puntos rojos/naranjas = encuestas con flag de georreferenciación fuera de zona."
        )

        # Secciones sin avance
        sin_avance = av_sec_all[av_sec_all["avance"] == 0]
        if not sin_avance.empty:
            st.markdown('<div class="sec-title">Secciones sin encuestas registradas</div>', unsafe_allow_html=True)
            st.write(", ".join(
                f"**{int(r['seccion'])}** ({r['localidad']}, {r['equipo']})"
                for _, r in sin_avance.iterrows()
            ))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — FLAGS DE CALIDAD Y SESGO
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if df.empty:
        st.info("Sin registros para los filtros seleccionados.")
    else:
        st.markdown('<div class="sec-title">Resumen de flags</div>', unsafe_allow_html=True)

        flag_cols_nivel = [c for c in df.columns if c.startswith("flag_") and c.endswith("_nivel")]
        resumen_flags = []
        for col in flag_cols_nivel:
            nombre = col.replace("flag_", "").replace("_nivel", "").replace("_", " ").title()
            n_rojo = int((df[col] == "rojo").sum())
            n_amarillo = int((df[col] == "amarillo").sum())
            n_total = len(df)
            resumen_flags.append({
                "flag": nombre,
                "rojo": n_rojo, "amarillo": n_amarillo,
                "sin_flag": max(n_total - n_rojo - n_amarillo, 0),
                "pct_afectado": round(100 * (n_rojo + n_amarillo) / n_total, 1) if n_total else 0,
            })

        rf = pd.DataFrame(resumen_flags)

        n_con_flag = int((df["flags_rojo_n"] + df["flags_amarillo_n"] > 0).sum())
        n_rojo_tot = int((df["flags_rojo_n"] > 0).sum())

        kc1, kc2, kc3 = st.columns(3)
        kpi(kc1, f"{n_con_flag:,}", "Registros con ≥1 flag",
            f"{round(100*n_con_flag/max(len(df),1),1)}% del total en vista",
            "amarillo" if n_con_flag else "")
        kpi(kc2, f"{n_rojo_tot:,}", "Con flag rojo (revisión prioritaria)",
            f"{round(100*n_rojo_tot/max(len(df),1),1)}% del total en vista",
            "rojo" if n_rojo_tot else "")
        kpi(kc3, f"{len(df):,}", "Total registros en vista", "")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Barra horizontal apilada: una fila por tipo de flag ─────────────────
        rf_plot = rf.sort_values("pct_afectado", ascending=True)
        fig_flags = px.bar(
            rf_plot, y="flag", x=["rojo", "amarillo", "sin_flag"], orientation="h",
            color_discrete_map={"rojo": ROJO, "amarillo": AMARILLO, "sin_flag": "#E3E7EC"},
            labels={"value": "Registros", "flag": "", "variable": ""},
            title="Registros marcados por tipo de flag",
            height=max(220, 70 * len(rf_plot)),
        )
        fig_flags.update_layout(
            barmode="stack", plot_bgcolor="white", paper_bgcolor="white",
            font_family="IBM Plex Sans", margin=dict(t=45, b=10, l=10),
            legend_title_text="", legend=dict(orientation="h", y=-0.15),
        )
        fig_flags.for_each_trace(lambda t: t.update(
            name={"rojo": "Rojo", "amarillo": "Amarillo", "sin_flag": "Sin flag"}.get(t.name, t.name)
        ))
        st.plotly_chart(fig_flags, use_container_width=True)

        with st.expander("Ver tabla de conteos por flag"):
            tbl_rf = rf[["flag", "rojo", "amarillo", "pct_afectado"]].copy()
            tbl_rf.columns = ["Flag", "🔴 Rojo", "🟡 Amarillo", "% afectado"]
            st.dataframe(
                tbl_rf.style.format({"% afectado": "{:.1f}%"})
                .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
                use_container_width=True, hide_index=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Tabla de registros con flags ───────────────────────────────────────
        st.markdown('<div class="sec-title">Registros con flags activos</div>', unsafe_allow_html=True)

        tipo_flag_opts = ["Todos"] + [c.replace("flag_", "").replace("_nivel", "").replace("_", " ").title()
                                       for c in flag_cols_nivel]
        nivel_opts = ["Todos", "rojo", "amarillo"]

        fc1, fc2 = st.columns(2)
        with fc1:
            tipo_flag_sel = st.selectbox("Tipo de flag", tipo_flag_opts)
        with fc2:
            nivel_sel = st.selectbox("Nivel", nivel_opts)

        df_flags = df[df["flags_rojo_n"] + df["flags_amarillo_n"] > 0].copy()

        if tipo_flag_sel != "Todos":
            col_target = "flag_" + tipo_flag_sel.lower().replace(" ", "_") + "_nivel"
            df_flags = df_flags[df_flags[col_target].notna()]
            if nivel_sel != "Todos":
                df_flags = df_flags[df_flags[col_target] == nivel_sel]
        elif nivel_sel != "Todos":
            mask = pd.Series(False, index=df_flags.index)
            for col in flag_cols_nivel:
                mask |= (df_flags[col] == nivel_sel)
            df_flags = df_flags[mask]

        cols_mostrar = [
            "folio", "seccion_electoral", "equipo", "encuestador_nombre",
            "duracion_min", "flags_rojo_n", "flags_amarillo_n",
        ] + flag_cols_nivel
        cols_mostrar = [c for c in cols_mostrar if c in df_flags.columns]

        st.dataframe(
            df_flags[cols_mostrar].sort_values(["flags_rojo_n", "flags_amarillo_n"], ascending=False),
            use_container_width=True, hide_index=True,
            height=min(80 + len(df_flags) * 35, 480),
        )
        st.caption(f"{len(df_flags):,} de {len(df):,} registros en vista tienen al menos un flag activo.")

        # ── Cobertura geográfica desbalanceada (a nivel sección) ───────────────
        st.markdown('<div class="sec-title">Cobertura geográfica desbalanceada (por sección)</div>', unsafe_allow_html=True)
        cob = flags.resumen_cobertura_desbalanceada(df_raw)
        cob_flag = cob[cob["flag_cobertura"]]
        if cob_flag.empty:
            st.success("Sin secciones con cobertura desbalanceada detectada.")
        else:
            tbl_cob = cob_flag[["seccion", "localidad", "equipo", "meta", "avance", "pct", "flag_cobertura_nivel"]].copy()
            tbl_cob.columns = ["Sección", "Localidad", "Equipo", "Meta", "Avance", "% Avance", "Nivel"]
            st.dataframe(
                tbl_cob.style
                .map(color_semaforo, subset=["Nivel"])
                .format({"% Avance": "{:.1f}%"})
                .set_properties(**{"font-family": "IBM Plex Sans", "font-size": "13px"}),
                use_container_width=True, hide_index=True,
            )



# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — RESULTADOS DEL INSTRUMENTO  (solo rol estatal)
# ══════════════════════════════════════════════════════════════════════════════
if tab4 is not None:
    with tab4:
        if df.empty:
            st.info("Sin registros para los filtros seleccionados.")
        else:
            # ── Perfil sociodemográfico ─────────────────────────────────────────
            st.markdown('<div class="sec-title">Perfil sociodemográfico</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                show_chart(pct_bar(df, "sexo", "Sexo"))
            with c2:
                show_chart(pct_bar(df, "rango_edad", "Rango de edad",
                                    orden=["18-29", "30-44", "45-59", "60+"]))
            with c3:
                show_chart(pct_bar(df, "ine", "¿Cuenta con INE?", orden=["Sí", "No"], colors=[VERDE, "#ccc"]))

            # Pirámide de edades
            df_pir = df.copy()
            df_pir["edad"] = pd.to_numeric(df_pir["edad"], errors="coerce")
            df_pir = df_pir.dropna(subset=["edad"])
            if len(df_pir) > 0:
                df_pir["grupo_edad"] = pd.cut(
                    df_pir["edad"], bins=[17, 29, 44, 59, 120],
                    labels=["18-29", "30-44", "45-59", "60+"]
                )
                pir = df_pir.groupby(["grupo_edad", "sexo"]).size().reset_index(name="n")
                pir = pir[pir["sexo"].isin(["Hombre", "Mujer"])]
                pir.loc[pir["sexo"] == "Hombre", "n"] *= -1
                if not pir.empty:
                    max_val = pir["n"].abs().max()
                    ticks_pos = list(range(0, int(max_val) + 5, max(int(max_val // 4), 1)))
                    ticks_val = [-t for t in reversed(ticks_pos[1:])] + ticks_pos
                    fig_p = px.bar(pir, x="n", y="grupo_edad", color="sexo", orientation="h",
                                   color_discrete_map={"Hombre": AZUL_L, "Mujer": NARANJA},
                                   labels={"n": "Conteo", "grupo_edad": ""},
                                   title="Pirámide de edades", height=300)
                    fig_p.update_xaxes(tickvals=ticks_val, ticktext=[abs(t) for t in ticks_val])
                    fig_p.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                        font_family="IBM Plex Sans", margin=dict(t=40, b=10))
                    st.plotly_chart(fig_p, use_container_width=True)

            st.markdown("---")

            # ── Bloque 4 — Principal problema del estado ────────────────────────
            st.markdown('<div class="sec-title">Bloque 4 — Dirección del estado</div>', unsafe_allow_html=True)
            show_chart(pct_bar(df, "direccion_estado", "P1. ¿El estado va por buen camino?", height=240))

            # ── Bloque 5 — Identificación partidista e intención de voto ───────
            st.markdown('<div class="sec-title">Bloque 5 — Afinidad partidista e intención de voto</div>', unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                show_chart(pct_bar(df, "identificacion_partidaria", "P4. Identificación partidista"))
            with b2:
                show_chart(pct_bar(df, "intencion_voto_principal", "P5. Intención de voto principal"))

            st.markdown("---")

            # ── Bloques 6 y 7 — Conocimiento, opinión y atributos por candidato ──
            st.markdown('<div class="sec-title">Bloques 6 y 7 — Conocimiento, opinión y atributos por aspirante</div>',
                        unsafe_allow_html=True)

            # Comparativo "conoce / opina bien" entre los 5 candidatos
            cc1, cc2 = st.columns(2)
            conoce_rows, opina_rows = [], []
            for cand, nombre in CANDIDATOS.items():
                col_conoce = f"conocimiento_{cand}"
                col_opina  = f"opinion_{cand}"
                if col_conoce in df.columns:
                    sub = df[col_conoce].dropna()
                    if len(sub):
                        pct_conoce = round((sub.astype(str).str.lower().str.contains("sí|si", regex=True)).mean() * 100, 1)
                        conoce_rows.append({"Candidato": nombre, "% Lo conoce": pct_conoce})
                if col_opina in df.columns:
                    sub = df[col_opina].dropna()
                    if len(sub):
                        opina_rows.append({"Candidato": nombre, "n respuestas": len(sub)})

            with cc1:
                if conoce_rows:
                    df_conoce = pd.DataFrame(conoce_rows).sort_values("% Lo conoce", ascending=True)
                    fig_c = px.bar(df_conoce, x="% Lo conoce", y="Candidato", orientation="h",
                                   text=df_conoce["% Lo conoce"].apply(lambda v: f"{v}%"),
                                   color_discrete_sequence=[VERDE_L],
                                   title="Bloque 6 — % que conoce a cada aspirante", height=300)
                    fig_c.update_traces(textposition="outside")
                    fig_c.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                        showlegend=False, font_family="IBM Plex Sans",
                                        margin=dict(t=45, b=5, l=160), xaxis_range=[0, 105])
                    st.plotly_chart(fig_c, use_container_width=True)
                else:
                    st.info("Sin datos de conocimiento de aspirantes.")

            with cc2:
                cand_sel = st.selectbox(
                    "Seleccionar aspirante — detalle Bloque 6 / 7",
                    list(CANDIDATOS.items()), format_func=lambda kv: kv[1], key="cand_sel",
                )
                cand_key, cand_nombre = cand_sel
                show_chart(pct_bar(df, f"opinion_{cand_key}", f"P9. Opinión sobre {cand_nombre}"))

            st.markdown(f"**Bloque 7 — Evaluación de atributos: {cand_nombre}**")
            atrib_cols_b7 = st.columns(4)
            for i, atrib in enumerate(ATRIBUTOS_BLOQUE7):
                campo = f"{atrib}_{cand_key}"
                with atrib_cols_b7[i % 4]:
                    show_chart(pct_bar(df, campo, atrib.replace("_", " ").title(), height=200))

            st.markdown("---")

            # ── Bloque 8 — Preferencia MORENA ────────────────────────────────────
            st.markdown('<div class="sec-title">Bloque 8 — Preferencia de candidato(a) MORENA</div>', unsafe_allow_html=True)
            show_chart(pct_bar(df, "preferencia_total_morena", "P19. Preferencia total MORENA", height=280))

            # ── Bloque 9 — Careos ────────────────────────────────────────────────
            st.markdown('<div class="sec-title">Bloque 9 — Careo a la gubernatura</div>', unsafe_allow_html=True)
            cc3, cc4 = st.columns(2)
            with cc3:
                show_chart(pct_bar(df, "careo_1", "P20. Careo 1"))
            with cc4:
                show_chart(pct_bar(df, "careo_2", "P21. Careo 2"))

            # ── Bloque 10 — Evaluación de autoridades ────────────────────────────
            st.markdown('<div class="sec-title">Bloque 10 — Evaluación de autoridades</div>', unsafe_allow_html=True)
            cc5, cc6, cc7 = st.columns(3)
            with cc5:
                show_chart(pct_bar(df, "aprobacion_zacatlan", "P22.1 Aprobación — Beatriz Sánchez Galindo"))
            with cc6:
                show_chart(pct_bar(df, "aprobacion_gobernador", "P22.2 Aprobación — Alejandro Armenta Mier"))
            with cc7:
                show_chart(pct_bar(df, "aprobacion_presidenta", "P22.3 Aprobación — Claudia Sheinbaum Pardo"))