"""
Zacatlán PIE · config.py (Encuesta L2)
Parámetros centralizados para el visualizador de monitoreo y auditoría.
Editar aquí — no tocar app.py / kpis.py / flags.py para cambiar umbrales o mapeos.

Fuentes:
  - Diccionario_Referencia_Zacatlán_version_lite.xlsx
  - Guia_Coordinadores_L2_Zacatlan_120626.xlsx
  - SECCION.shp (catálogo seccional Puebla, IEE/INE) — municipio=208 → Zacatlán
"""

# ── API Bubble ──────────────────────────────────────────────────────────────
# Confirmado por PO de Bubble (Zacatlán):
#   Data API root: https://encuesta-aspirante-zacatlan-vl.bubbleapps.io/api/1.1/obj
# TODO: confirmar nombre exacto del "Thing type" — se asume "Encuesta" por
# consistencia con Guerrero; ajustar si test_conexion_bubble.py da 404.
BUBBLE_BASE_URL  = "https://encuesta-aspirante-zacatlan-vl.bubbleapps.io/api/1.1"
BUBBLE_ENDPOINT  = f"{BUBBLE_BASE_URL}/obj/Encuesta"
BUBBLE_PAGE_SIZE = 100
CACHE_TTL_SEC    = 3600          # 1 hora — ajustar si el operativo requiere refresh más frecuente

# ── Calendario de operativo ───────────────────────────────────────────────────
# Fin de semana 1 (Submódulo A, Panel L1): 13–14 junio 2026 · 19 secciones · meta 430
# Fin de semana 2 (Submódulo B, Ampliación L2): 20–21 junio 2026 · 8 secciones · meta 400
INICIO_OPERATIVO = "2026-06-13"

FECHAS_SUBMODULO = {
    "A": ["2026-06-13", "2026-06-14"],
    "B": ["2026-06-20", "2026-06-21"],
}

# ── Umbrales de calidad (flags) ────────────────────────────────────────────────
# TODO CONFIRMAR: cuestionario tiene 126 campos (70 solo en Bloque 7: 5 candidatos
# × 7 atributos). Valores Guerrero (5/20 min) eran para cuestionario ~30 campos;
# placeholders ajustados a la baja/alza en lo que se valida con stakeholder.
DUR_MIN_MIN = 8     # TODO: confirmar duración mínima creíble (minutos)
DUR_MAX_MIN = 40    # TODO: confirmar duración máxima creíble (minutos)

# Straightlining: n.º mínimo de respuestas idénticas dentro de una batería para
# disparar el flag (ver BATERIAS_STRAIGHTLINING más abajo — PROPUESTA a validar).
UMBRAL_STRAIGHTLINING_BLOQUE7 = 7   # batería completa (7 atributos) idéntica → rojo
UMBRAL_STRAIGHTLINING_BLOQUE6 = 5   # batería completa (5 candidatos) idéntica → amarillo

# Horario operativo esperado para detección de levantamientos atípicos.
# TODO: confirmar rango horario real de campo (turno mañana/tarde).
HORA_INICIO_OPERATIVO = 8   # 08:00 hrs
HORA_FIN_OPERATIVO    = 19  # 19:00 hrs

AUTO_REFRESH_SEC = 300

# ── Identidad visual ───────────────────────────────────
VERDE    = "#2E7D5E"
VERDE_L  = "#52B788"
AZUL     = "#1A3A5C"
AZUL_L   = "#2C6E9E"
NARANJA  = "#E07B39"
ROJO     = "#C0392B"
AMARILLO = "#F5A623"
GRIS_BG  = "#F2F4F7"

# ── Mapeo campos Bubble → app (desde Diccionario_Referencia_Zacatlán) ─────────
# ⚠️  'P9_5_text' (sin "o") proviene tal cual del diccionario — el resto de la
#     serie P9 usa '..._texto'. Verificar contra un registro real de Bubble
#     antes de confiar en este key; si Bubble usa 'P9_5_texto', corregir aquí.
FIELD_MAP = {
    '_id'                         : 'id_unico',
    'Created Date'                : 'fecha_creacion',
    'Modified Date'               : 'fecha_modificacion',
    'Created By'                  : 'user_creador',
    'nombre_encuestador'          : 'nombre_encuestador',
    'coordinador'                 : 'coordinador',
    'seccion_electoral'           : 'seccion_electoral',
    'municipio_texto'             : 'municipio_texto',
    'google_address'              : 'google_address',
    'latitud'                     : 'latitud',
    'longitud'                    : 'longitud',
    'A'                           : 'codigo_sexo',
    'A_texto'                     : 'sexo',
    'B'                           : 'edad',
    'B_98'                        : 'codigo_rango_edad',
    'B_98_texto'                  : 'rango_edad',
    'C'                           : 'codigo_ine',
    'C_texto'                     : 'ine',
    'P1'                          : 'codigo_direccion_estado',
    'P1_texto'                    : 'direccion_estado',
    'P4'                          : 'codigo_identificacion_partidaria',
    'P4_texto'                    : 'identificacion_partidaria',
    'P5'                          : 'codigo_intencion_voto_principal',
    'P5_texto'                    : 'intencion_voto_principal',
    'P8_1'                        : 'codigo_conocimiento_jcly',
    'P8_1_texto'                  : 'conocimiento_jcly',
    'P8_2'                        : 'codigo_conocimiento_beatriz',
    'P8_2_texto'                  : 'conocimiento_beatriz',
    'P8_3'                        : 'codigo_conocimiento_asdruval',
    'P8_3_texto'                  : 'conocimiento_asdruval',
    'P8_4'                        : 'codigo_conocimiento_luis',
    'P8_4_texto'                  : 'conocimiento_luis',
    'P8_5'                        : 'codigo_conocimiento_eybar',
    'P8_5_texto'                  : 'conocimiento_eybar',
    'P9_1'                        : 'codigo_opinion_jcly',
    'P9_1_texto'                  : 'opinion_jcly',
    'P9_2'                        : 'codigo_opinion_beatriz',
    'P9_2_texto'                  : 'opinion_beatriz',
    'P9_3'                        : 'codigo_opinion_asdruval',
    'P9_3_texto'                  : 'opinion_asdruval',
    'P9_4'                        : 'codigo_opinion_luis',
    'P9_4_texto'                  : 'opinion_luis',
    'P9_5'                        : 'codigo_opinion_eybar',
    'P9_5_text'                   : 'opinion_eybar',
    'P10_1'                       : 'codigo_honestidad_jcly',
    'P10_1_texto'                 : 'honestidad_jcly',
    'P10_2'                       : 'codigo_honestidad_beatriz',
    'P10_2_texto'                 : 'honestidad_beatriz',
    'P10_3'                       : 'codigo_honestidad_asdruval',
    'P10_3_texto'                 : 'honestidad_asdruval',
    'P10_4'                       : 'codigo_honestidad_luis',
    'P10_4_texto'                 : 'honestidad_luis',
    'P10_5'                       : 'codigo_honestidad_eybar',
    'P10_5_texto'                 : 'honestidad_eybar',
    'P11_1'                       : 'codigo_cercania_jcly',
    'P11_1_texto'                 : 'cercania_jcly',
    'P11_2'                       : 'codigo_cercania_beatriz',
    'P11_2_texto'                 : 'cercania_beatriz',
    'P11_3'                       : 'codigo_cercania_asdruval',
    'P11_3_texto'                 : 'cercania_asdruval',
    'P11_4'                       : 'codigo_cercania_luis',
    'P11_4_texto'                 : 'cercania_luis',
    'P11_5'                       : 'codigo_cercania_eybar',
    'P11_5_texto'                 : 'cercania_eybar',
    'P12_1'                       : 'codigo_derecho_mujeres_jcly',
    'P12_1_texto'                 : 'derecho_mujeres_jcly',
    'P12_2'                       : 'codigo_derecho_mujeres_beatriz',
    'P12_2_texto'                 : 'derecho_mujeres_beatriz',
    'P12_3'                       : 'codigo_derecho_mujeres_asdruval',
    'P12_3_texto'                 : 'derecho_mujeres_asdruval',
    'P12_4'                       : 'codigo_derecho_mujeres_luis',
    'P12_4_texto'                 : 'derecho_mujeres_luis',
    'P12_5'                       : 'codigo_derecho_mujeres_eybar',
    'P12_5_texto'                 : 'derecho_mujeres_eybar',
    'P13_1'                       : 'codigo_conocimiento_estado_jcly',
    'P13_1_texto'                 : 'conocimiento_estado_jcly',
    'P13_2'                       : 'codigo_conocimiento_estado_beatriz',
    'P13_2_texto'                 : 'conocimiento_estado_beatriz',
    'P13_3'                       : 'codigo_conocimiento_estado_asdruval',
    'P13_3_texto'                 : 'conocimiento_estado_asdruval',
    'P13_4'                       : 'codigo_conocimiento_estado_luis',
    'P13_4_texto'                 : 'conocimiento_estado_luis',
    'P13_5'                       : 'codigo_conocimiento_estado_eybar',
    'P13_5_texto'                 : 'conocimiento_estado_eybar',
    'P14_1'                       : 'codigo_cumplimiento_jcly',
    'P14_1_texto'                 : 'cumplimiento_jcly',
    'P14_2'                       : 'codigo_cumplimiento_beatriz',
    'P14_2_texto'                 : 'cumplimiento_beatriz',
    'P14_3'                       : 'codigo_cumplimiento_asdruval',
    'P14_3_texto'                 : 'cumplimiento_asdruval',
    'P14_4'                       : 'codigo_cumplimiento_luis',
    'P14_4_texto'                 : 'cumplimiento_luis',
    'P14_5'                       : 'codigo_cumplimiento_eybar',
    'P14_5_texto'                 : 'cumplimiento_eybar',
    'P15_1'                       : 'codigo_buena_candidatura_jcly',
    'P15_1_texto'                 : 'buena_candidatura_jcly',
    'P15_2'                       : 'codigo_buena_candidatura_beatriz',
    'P15_2_texto'                 : 'buena_candidatura_beatriz',
    'P15_3'                       : 'codigo_buena_candidatura_asdruval',
    'P15_3_texto'                 : 'buena_candidatura_asdruval',
    'P15_4'                       : 'codigo_buena_candidatura_luis',
    'P15_4_texto'                 : 'buena_candidatura_luis',
    'P15_5'                       : 'codigo_buena_candidatura_eybar',
    'P15_5_texto'                 : 'buena_candidatura_eybar',
    'P16_1'                       : 'codigo_votar_o_no_jcly',
    'P16_1_texto'                 : 'votar_o_no_jcly',
    'P16_2'                       : 'codigo_votar_o_no_beatriz',
    'P16_2_texto'                 : 'votar_o_no_beatriz',
    'P16_3'                       : 'codigo_votar_o_no_asdruval',
    'P16_3_texto'                 : 'votar_o_no_asdruval',
    'P16_4'                       : 'codigo_votar_o_no_luis',
    'P16_4_texto'                 : 'votar_o_no_luis',
    'P16_5'                       : 'codigo_votar_o_no_eybar',
    'P16_5_texto'                 : 'votar_o_no_eybar',
    'P19_1'                       : 'codigo_preferencia_total_morena',
    'P19_1_texto'                 : 'preferencia_total_morena',
    'P20'                         : 'codigo_careo_1',
    'P20_texto'                   : 'careo_1',
    'P21'                         : 'codigo_careo_2',
    'P21_texto'                   : 'careo_2',
    'P22_1'                       : 'codigo_aprobacion_zacatlan',
    'P22_1_texto'                 : 'aprobacion_zacatlan',
    'P22_2'                       : 'codigo_aprobacion_gobernador',
    'P22_2_texto'                 : 'aprobacion_gobernador',
    'P22_3'                       : 'codigo_aprobacion_presidenta',
    'P22_3_texto'                 : 'aprobacion_presidenta',
}

# ── Campos que NO deben mostrarse en el dashboard público ─────────────────────
# (se conservan en el DataFrame interno: latitud/longitud se requieren para el
#  flag de georreferenciación fuera de zona; user_creador para encuestador_id)
CAMPOS_OCULTAR_DISPLAY = {
    "google_address", "latitud", "longitud", "user_creador",
}

CAMPOS_EXCLUIR = set()  # placeholder — sin PII de nombre/celular/email en el diccionario lite

# ── Bloques del cuestionario (para navegación / desagregación temática) ───────
# NOTA: estas son "secciones del CUESTIONARIO" — no confundir con "seccion
# electoral" (geografía). Las metas/avance del dashboard se calculan sobre
# seccion electoral (ver METAS_POR_SECCION).
BLOQUES = {
    "Bloque 1: Datos de captura": [
        "id_unico", "fecha_creacion", "fecha_modificacion", "user_creador",
        "nombre_encuestador", "coordinador",
    ],
    "Bloque 2: Identificación de vivienda": [
        "seccion_electoral", "municipio_texto", "google_address", "latitud", "longitud",
    ],
    "Bloque 3: Sexo, Edad, INE": [
        "codigo_sexo", "sexo", "edad", "codigo_rango_edad", "rango_edad", "codigo_ine", "ine",
    ],
    "Bloque 4: Principal problema del estado": [
        "codigo_direccion_estado", "direccion_estado",
    ],
    "Bloque 5: Intención de voto y afinidad partidista": [
        "codigo_identificacion_partidaria", "identificacion_partidaria",
        "codigo_intencion_voto_principal", "intencion_voto_principal",
    ],
    "Bloque 6: Conocimiento y opinión de aspirantes": [
        c for cand in ("jcly", "beatriz", "asdruval", "luis", "eybar")
        for c in (f"codigo_conocimiento_{cand}", f"conocimiento_{cand}",
                  f"codigo_opinion_{cand}", f"opinion_{cand}")
    ],
    "Bloque 7: Evaluación de atributos de aspirantes": [
        c for atributo in ("honestidad", "cercania", "derecho_mujeres",
                            "conocimiento_estado", "cumplimiento",
                            "buena_candidatura", "votar_o_no")
        for cand in ("jcly", "beatriz", "asdruval", "luis", "eybar")
        for c in (f"codigo_{atributo}_{cand}", f"{atributo}_{cand}")
    ],
    "Bloque 8: Preferencia candidato(a) MORENA": [
        "codigo_preferencia_total_morena", "preferencia_total_morena",
    ],
    "Bloque 9: Careo a la gubernatura": [
        "codigo_careo_1", "careo_1", "codigo_careo_2", "careo_2",
    ],
    "Bloque 10: Evaluación de autoridades": [
        "codigo_aprobacion_zacatlan", "aprobacion_zacatlan",
        "codigo_aprobacion_gobernador", "aprobacion_gobernador",
        "codigo_aprobacion_presidenta", "aprobacion_presidenta",
    ],
}

CANDIDATOS = {
    "jcly":     "Juan Carlos Lastiri Yamal",
    "beatriz":  "Beatriz Sánchez Galindo",
    "asdruval": "Asdruval Drake Hurtado",
    "luis":     "Luis Márquez Lecona",
    "eybar":    "Eybar Márquez Manzano",
}

ATRIBUTOS_BLOQUE7 = [
    "honestidad", "cercania", "derecho_mujeres", "conocimiento_estado",
    "cumplimiento", "buena_candidatura", "votar_o_no",
]

# ── Baterías candidatas a straightlining (PROPUESTA — validar escalas reales) ─
# Cada entrada: lista de columnas 'codigo_*' que comparten la misma escala de
# respuesta y se presentan consecutivamente al entrevistado. Si todas las
# respuestas dentro de una batería son idénticas, se considera straightlining.
#
# Bloque 7 → 5 baterías "por candidato" (7 ítems c/u: un atributo por pregunta).
# Bloque 6 → 2 baterías "por pregunta" (5 ítems c/u: un candidato por pregunta).
BATERIAS_STRAIGHTLINING = {
    **{
        f"bloque7_{cand}": [f"codigo_{atributo}_{cand}" for atributo in ATRIBUTOS_BLOQUE7]
        for cand in CANDIDATOS
    },
    "bloque6_conocimiento": [f"codigo_conocimiento_{cand}" for cand in CANDIDATOS],
    "bloque6_opinion":      [f"codigo_opinion_{cand}"      for cand in CANDIDATOS],
}

# ── Geografía / Shapefile seccional ───────────────────────────────────────────
# Shapefile original: SECCION.shp (catálogo estatal Puebla, proyección
# WGS_1984_UTM_Zone_14N). Reproyectado a WGS84 y filtrado a municipio=208
# (Zacatlán) → secciones_zacatlan.geojson (33 secciones; 27 en muestra).
ENTIDAD               = 21    # Puebla (catálogo IEE/INE)
CLAVE_MUNICIPIO       = 208   # Zacatlán
GEOJSON_SECCIONES     = "secciones_zacatlan.geojson"
ZACATLAN_CENTRO       = [19.9536, -97.9811]
ZACATLAN_ZOOM         = 12

# Secciones del municipio NO incluidas en la muestra del operativo (se muestran
# en el mapa en gris, sin meta/avance).
SECCIONES_FUERA_MUESTRA = [2464, 2466, 2469, 2483, 2489, 2896]

# ── Metas por sección electoral (Guía Coordinadores L2 — 12/06/2026) ──────────
# meta_encuestas: meta de encuestas levantadas por sección.
# total_viv_visitar: meta mínima de puertas a tocar (puede ser > meta_encuestas).
# cuotas: meta de encuestas por sexo (H/M) y rango de edad — para flag de
#         "cobertura de cuotas desbalanceada".
METAS_POR_SECCION = {2460: {'tipo': 'Urbano',
        'submodulo': 'B',
        'localidad': 'Centro Escolar',
        'equipo': 'Carlos',
        'ln_mayo2026': 1604,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': None},
 2461: {'tipo': 'Urbano',
        'submodulo': 'A',
        'localidad': 'Jardin Beatriz Núñez',
        'equipo': 'Areli',
        'ln_mayo2026': 1447,
        'meta_encuestas': 15,
        'total_viv_visitar': 16,
        'cuotas': {'18-29': {'H': 2, 'M': 2},
                   '30-44': {'H': 2, 'M': 3},
                   '45-59': {'H': 2, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': None},
 2462: {'tipo': 'Urbano',
        'submodulo': 'B',
        'localidad': 'Bachillerato Baudelio Serafin',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1360,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': None},
 2463: {'tipo': 'Urbano',
        'submodulo': 'A',
        'localidad': 'Jardin La Ciénega',
        'equipo': 'Areli',
        'ln_mayo2026': 1455,
        'meta_encuestas': 15,
        'total_viv_visitar': 16,
        'cuotas': {'18-29': {'H': 2, 'M': 2},
                   '30-44': {'H': 2, 'M': 3},
                   '45-59': {'H': 2, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': None},
 2465: {'tipo': 'Urbano',
        'submodulo': 'A',
        'localidad': 'Anexa',
        'equipo': 'Areli',
        'ln_mayo2026': 1908,
        'meta_encuestas': 19,
        'total_viv_visitar': 20,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 3},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': None},
 2467: {'tipo': 'Urbano',
        'submodulo': 'A',
        'localidad': 'Montessori',
        'equipo': 'Areli',
        'ln_mayo2026': 1189,
        'meta_encuestas': 12,
        'total_viv_visitar': 12,
        'cuotas': {'18-29': {'H': 2, 'M': 2},
                   '30-44': {'H': 2, 'M': 1},
                   '45-59': {'H': 1, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': None},
 2470: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Camotepec',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1846,
        'meta_encuestas': 19,
        'total_viv_visitar': 20,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 3},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '1 localidad(es) sin amanzanar'},
 2471: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Tepeixco',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 2067,
        'meta_encuestas': 21,
        'total_viv_visitar': 22,
        'cuotas': {'18-29': {'H': 4, 'M': 4},
                   '30-44': {'H': 4, 'M': 2},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': 'Localidades sin amanzanar — contar viviendas en campo'},
 2472: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'San Cristóbal',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 2798,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': 'Localidades sin amanzanar — contar viviendas en campo'},
 2473: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Xoxonacatla',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1966,
        'meta_encuestas': 20,
        'total_viv_visitar': 20,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 4},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': 'Localidades sin amanzanar — contar viviendas en campo'},
 2474: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Hueyapan',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1710,
        'meta_encuestas': 17,
        'total_viv_visitar': 18,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 2},
                   '45-59': {'H': 2, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '4 localidad(es) sin amanzanar'},
 2475: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Las Lajas',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1903,
        'meta_encuestas': 19,
        'total_viv_visitar': 20,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 3},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '4 localidad(es) sin amanzanar'},
 2476: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'Nanacamila',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1039,
        'meta_encuestas': 50,
        'total_viv_visitar': 52,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': 'Localidades sin amanzanar — contar viviendas en campo'},
 2477: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'Matlahuacala',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 931,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': '4 localidad(es) sin amanzanar'},
 2478: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Jicolapa',
        'equipo': 'Mayra',
        'ln_mayo2026': 3737,
        'meta_encuestas': 38,
        'total_viv_visitar': 39,
        'cuotas': {'18-29': {'H': 6, 'M': 6},
                   '30-44': {'H': 6, 'M': 7},
                   '45-59': {'H': 4, 'M': 5},
                   '60+': {'H': 3, 'M': 1}},
        'observaciones': '3 manzanas (ajuste por carga) · 1 localidad(es) sin amanzanar'},
 2480: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Ayehualulco',
        'equipo': 'Juan Carlos',
        'ln_mayo2026': 4094,
        'meta_encuestas': 42,
        'total_viv_visitar': 44,
        'cuotas': {'18-29': {'H': 7, 'M': 7},
                   '30-44': {'H': 7, 'M': 7},
                   '45-59': {'H': 4, 'M': 6},
                   '60+': {'H': 3, 'M': 1}},
        'observaciones': 'Sección grande — doble peso en L1 · 1 localidad(es) sin amanzanar'},
 2481: {'tipo': 'Mixto',
        'submodulo': 'A',
        'localidad': 'Cuautilulco',
        'equipo': 'Juan Carlos',
        'ln_mayo2026': 4665,
        'meta_encuestas': 48,
        'total_viv_visitar': 48,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 8},
                   '45-59': {'H': 5, 'M': 6},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': None},
 2482: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Tlatempa',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1792,
        'meta_encuestas': 18,
        'total_viv_visitar': 18,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 3},
                   '45-59': {'H': 2, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '1 localidad(es) sin amanzanar'},
 2484: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Maquixtla',
        'equipo': 'Carlos',
        'ln_mayo2026': 3714,
        'meta_encuestas': 38,
        'total_viv_visitar': 40,
        'cuotas': {'18-29': {'H': 6, 'M': 6},
                   '30-44': {'H': 6, 'M': 7},
                   '45-59': {'H': 4, 'M': 5},
                   '60+': {'H': 3, 'M': 1}},
        'observaciones': 'Sección grande — doble peso en L1 · 2 localidad(es) sin amanzanar'},
 2485: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Tomatlán',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1426,
        'meta_encuestas': 15,
        'total_viv_visitar': 16,
        'cuotas': {'18-29': {'H': 2, 'M': 2},
                   '30-44': {'H': 2, 'M': 3},
                   '45-59': {'H': 2, 'M': 2},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '1 localidad(es) sin amanzanar'},
 2486: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'San Joaquín',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1532,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': '4 localidad(es) sin amanzanar'},
 2487: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'San Miguel',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1721,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': '1 localidad(es) sin amanzanar'},
 2488: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Zoquitla',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 662,
        'meta_encuestas': 7,
        'total_viv_visitar': 8,
        'cuotas': {'18-29': {'H': 1, 'M': 1},
                   '30-44': {'H': 1, 'M': 1},
                   '45-59': {'H': 1, 'M': 1},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': 'Localidades sin amanzanar — contar viviendas en campo · Manzanas pequeñas — tomar '
                         'todas las viviendas'},
 2727: {'tipo': 'Urbano',
        'submodulo': 'A',
        'localidad': 'Esc. Federal',
        'equipo': 'Areli',
        'ln_mayo2026': 2026,
        'meta_encuestas': 21,
        'total_viv_visitar': 22,
        'cuotas': {'18-29': {'H': 4, 'M': 4},
                   '30-44': {'H': 4, 'M': 2},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': None},
 2808: {'tipo': 'Rural',
        'submodulo': 'B',
        'localidad': 'Eloxochitlán',
        'equipo': 'Mayra',
        'ln_mayo2026': 1244,
        'meta_encuestas': 50,
        'total_viv_visitar': 50,
        'cuotas': {'18-29': {'H': 8, 'M': 8},
                   '30-44': {'H': 8, 'M': 9},
                   '45-59': {'H': 5, 'M': 7},
                   '60+': {'H': 3, 'M': 2}},
        'observaciones': None},
 2809: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Eloxochitlán',
        'equipo': 'Sin asignar',
        'ln_mayo2026': 1921,
        'meta_encuestas': 20,
        'total_viv_visitar': 20,
        'cuotas': {'18-29': {'H': 3, 'M': 3},
                   '30-44': {'H': 3, 'M': 4},
                   '45-59': {'H': 2, 'M': 3},
                   '60+': {'H': 1, 'M': 1}},
        'observaciones': '1 localidad(es) sin amanzanar'},
 2895: {'tipo': 'Rural',
        'submodulo': 'A',
        'localidad': 'Atzingo',
        'equipo': 'Mayra',
        'ln_mayo2026': 2584,
        'meta_encuestas': 26,
        'total_viv_visitar': 26,
        'cuotas': {'18-29': {'H': 4, 'M': 4},
                   '30-44': {'H': 4, 'M': 5},
                   '45-59': {'H': 3, 'M': 3},
                   '60+': {'H': 2, 'M': 1}},
        'observaciones': '1 localidad(es) sin amanzanar'}}


META_GLOBAL = sum(v["meta_encuestas"] for v in METAS_POR_SECCION.values())  # 830
META_SUBMODULO = {
    "A": sum(v["meta_encuestas"] for v in METAS_POR_SECCION.values() if v["submodulo"] == "A"),  # 430
    "B": sum(v["meta_encuestas"] for v in METAS_POR_SECCION.values() if v["submodulo"] == "B"),  # 400
}

# ── Equipos / Coordinadores ────────────────────────────────────────────────────
EQUIPOS = sorted({v["equipo"] for v in METAS_POR_SECCION.values()})

SECCIONES_POR_EQUIPO: dict[str, list[int]] = {}
for _sec, _v in METAS_POR_SECCION.items():
    SECCIONES_POR_EQUIPO.setdefault(_v["equipo"], []).append(_sec)
for _eq in SECCIONES_POR_EQUIPO:
    SECCIONES_POR_EQUIPO[_eq].sort()

# ── Roles (streamlit-authenticator) ───────────────────────────────────────────
# Solo 3 usuarios supervisores — todos con rol "estatal" (acceso completo a los
# 4 tabs y a las 27 secciones). Si más adelante se necesita un rol "equipo"
# restringido por SECCIONES_POR_EQUIPO, agregar entradas con "rol": "equipo".
ROLES = {
    "omar": {
        "rol":       "estatal",
        "equipos":   EQUIPOS,
        "secciones": list(METAS_POR_SECCION.keys()),
    },
    "fernanda": {
        "rol":       "estatal",
        "equipos":   EQUIPOS,
        "secciones": list(METAS_POR_SECCION.keys()),
    },
    "juan_carlos": {
        "rol":       "estatal",
        "equipos":   EQUIPOS,
        "secciones": list(METAS_POR_SECCION.keys()),
    },
}