# -*- coding: utf-8 -*-
"""
Visor de restricciones ambientales — VIAPRO Consultoría
Sube un KMZ/KML del área de estudio y revisa automáticamente
las intersecciones con las capas ambientales precargadas en /capas.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ----------------------------- Configuración -----------------------------

CARPETA_CAPAS = Path(__file__).parent / "capas"
CRS_VISOR = 4326      # WGS84 para el mapa
CRS_AREAS = 9377      # MAGNA-SIRGAS / Origen Nacional (áreas en metros, Colombia)

VERDE_OSCURO = "#2F5233"
VERDE_SALVIA = "#B9C4B1"
CREMA = "#FAFAF7"

PALETA_CAPAS = [
    "#C0392B", "#E67E22", "#8E44AD", "#2980B9", "#16A085",
    "#D4AC0D", "#7B241C", "#1F618D", "#6C3483", "#117A65",
]

st.set_page_config(
    page_title="Visor de restricciones ambientales | VIAPRO",
    page_icon="🏔️",
    layout="wide",
)

st.markdown(
    f"""
    <style>
      .stApp {{ background-color: {CREMA}; }}
      h1, h2, h3 {{ color: {VERDE_OSCURO}; }}
      section[data-testid="stSidebar"] {{ background-color: #EFF2EC; }}
      div[data-testid="stFileUploader"] label p {{ font-weight: 600; }}
      .resumen-ok {{
        background: #E8F0E8; border-left: 6px solid {VERDE_OSCURO};
        padding: 0.8rem 1rem; border-radius: 6px;
      }}
      .resumen-alerta {{
        background: #FBEAE5; border-left: 6px solid #C0392B;
        padding: 0.8rem 1rem; border-radius: 6px;
      }}
      .stApp, .stApp p, .stApp label, .stApp li, .stApp span, .stMarkdown, div[data-testid="stCaptionContainer"] {{
      color: #2F5233 !important;
      }}
      section[data-testid="stSidebar"] * {{
      color: #2F5233 !important;
      }}
      div[data-testid="stFileUploader"] section {{
      background-color: #2B2C36 !important;
      }}
      div[data-testid="stFileUploader"] section * {{
      color: #E8F0E8 !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------- Carga de capas -----------------------------

@st.cache_resource(show_spinner="Cargando capas ambientales…")
def cargar_capas() -> dict:
    """Lee todas las capas de la carpeta /capas una sola vez (GeoJSON, GPKG o SHP)."""
    capas = {}
    if not CARPETA_CAPAS.exists():
        return capas
    rutas = sorted(
        list(CARPETA_CAPAS.glob("*.geojson"))
        + list(CARPETA_CAPAS.glob("*.gpkg"))
        + list(CARPETA_CAPAS.glob("*.shp"))
    )
    for ruta in rutas:
        try:
            if ruta.suffix == ".gpkg":
                import pyogrio
                for capa in pyogrio.list_layers(str(ruta))[:, 0]:
                    gdf = gpd.read_file(ruta, layer=capa)
                    capas[f"{ruta.stem} · {capa}"] = _preparar(gdf)
            else:
                gdf = gpd.read_file(ruta)
                capas[ruta.stem.replace("_", " ")] = _preparar(gdf)
        except Exception as e:  # una capa dañada no debe tumbar la app
            st.warning(f"No se pudo leer la capa {ruta.name}: {e}")
    return capas


def _preparar(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproyecta a WGS84 y corrige geometrías inválidas."""
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_VISOR)
    gdf = gdf.to_crs(CRS_VISOR)
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf[~gdf.geometry.is_empty]


# ----------------------------- Lectura del KMZ -----------------------------

def leer_kmz(archivo) -> gpd.GeoDataFrame | None:
    """Convierte el KMZ/KML subido en un GeoDataFrame en WGS84."""
    sufijo = Path(archivo.name).suffix.lower()
    contenido = archivo.read()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if sufijo == ".kmz":
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                kmls = [n for n in z.namelist() if n.lower().endswith(".kml")]
                if not kmls:
                    st.error("El KMZ no contiene ningún archivo KML.")
                    return None
                ruta_kml = tmp / "area.kml"
                ruta_kml.write_bytes(z.read(kmls[0]))
        else:
            ruta_kml = tmp / "area.kml"
            ruta_kml.write_bytes(contenido)

        try:
            import pyogrio
            partes = []
            for capa in pyogrio.list_layers(str(ruta_kml))[:, 0]:
                g = gpd.read_file(ruta_kml, layer=capa)
                if not g.empty:
                    partes.append(g)
            gdf = pd.concat(partes, ignore_index=True) if partes else gpd.read_file(ruta_kml)
        except Exception:
            gdf = gpd.read_file(ruta_kml)

    gdf = _preparar(gpd.GeoDataFrame(gdf, crs=gdf.crs or CRS_VISOR))
    # Nos quedamos con los polígonos; si solo hay líneas/puntos se avisa
    poligonos = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if poligonos.empty:
        st.error("El archivo no contiene polígonos. El área de estudio debe ser un polígono.")
        return None
    return poligonos


# ----------------------------- Análisis -----------------------------

def analizar(area: gpd.GeoDataFrame, capas: dict):
    """Intersecta el área de estudio con cada capa y arma la tabla de resultados."""
    area_m = area.to_crs(CRS_AREAS)
    ha_area = area_m.geometry.area.sum() / 10_000

    filas, intersecciones = [], {}
    for nombre, capa in capas.items():
        try:
            inter = gpd.overlay(area, capa, how="intersection", keep_geom_type=False)
            inter = inter[inter.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        except Exception as e:
            st.warning(f"Error al intersectar con {nombre}: {e}")
            continue

        if inter.empty:
            filas.append({"Capa": nombre, "¿Se cruza?": "✅ No",
                          "Área intersectada (ha)": 0.0, "% del área de estudio": 0.0})
        else:
            ha = inter.to_crs(CRS_AREAS).geometry.area.sum() / 10_000
            filas.append({"Capa": nombre, "¿Se cruza?": "⚠️ Sí",
                          "Área intersectada (ha)": round(ha, 2),
                          "% del área de estudio": round(100 * ha / ha_area, 2) if ha_area else 0})
            intersecciones[nombre] = inter

    tabla = pd.DataFrame(filas).sort_values("Área intersectada (ha)", ascending=False)
    return tabla, intersecciones, ha_area


# ----------------------------- Mapa -----------------------------

def construir_mapa(area, capas, intersecciones):
    centro = area.geometry.union_all().centroid
    m = folium.Map(location=[centro.y, centro.x], zoom_start=12, tiles=None)
    folium.TileLayer("OpenStreetMap", name="Mapa base").add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="Imagen satelital",
    ).add_to(m)

    # Capas ambientales completas (contexto, apagadas por defecto)
    for i, (nombre, capa) in enumerate(capas.items()):
        color = PALETA_CAPAS[i % len(PALETA_CAPAS)]
        folium.GeoJson(
            capa.to_json(), name=f"Capa: {nombre}", show=False,
            style_function=lambda _, c=color: {
                "color": c, "weight": 1, "fillColor": c, "fillOpacity": 0.15},
        ).add_to(m)

    # Intersecciones (encendidas)
    for i, (nombre, inter) in enumerate(intersecciones.items()):
        color = PALETA_CAPAS[i % len(PALETA_CAPAS)]
        folium.GeoJson(
            inter.to_json(), name=f"⚠️ Cruce: {nombre}",
            style_function=lambda _, c=color: {
                "color": c, "weight": 2, "fillColor": c, "fillOpacity": 0.55},
            tooltip=nombre,
        ).add_to(m)

    # Área de estudio encima
    folium.GeoJson(
        area.to_json(), name="Área de estudio",
        style_function=lambda _: {
            "color": VERDE_OSCURO, "weight": 3, "fillOpacity": 0.05, "dashArray": "6 4"},
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds(m.get_bounds())
    return m


# ----------------------------- Interfaz -----------------------------

col_logo, col_titulo = st.columns([1, 3])
with col_logo:
    logo = Path(__file__).parent / "assets" / "logo.jpg"
    if logo.exists():
        st.image(str(logo), width=220)
with col_titulo:
    st.title("Visor de restricciones ambientales")
    st.caption("Suba el KMZ del área de estudio para verificar cruces con las capas ambientales de revisión.")

capas = cargar_capas()

with st.sidebar:
    st.header("Área de estudio")
    archivo = st.file_uploader("Archivo KMZ o KML", type=["kmz", "kml"])
    st.divider()
    st.subheader("Capas precargadas")
    if capas:
        for n in capas:
            st.markdown(f"- {n}")
    else:
        st.info("No hay capas en la carpeta `capas/`. Agregue archivos GeoJSON, GPKG o SHP.")

if archivo is None:
    st.markdown(
        f"""<div class="resumen-ok">⬅️ Cargue el archivo <b>KMZ</b> del área de estudio en el
        panel izquierdo. Las capas de revisión ya están precargadas en la aplicación.</div>""",
        unsafe_allow_html=True,
    )
elif not capas:
    st.error("No hay capas precargadas para comparar.")
else:
    area = leer_kmz(archivo)
    if area is not None:
        tabla, intersecciones, ha_area = analizar(area, capas)
        n_cruces = len(intersecciones)

        if n_cruces:
            st.markdown(
                f"""<div class="resumen-alerta">⚠️ El área de estudio
                (<b>{ha_area:,.1f} ha</b>) presenta cruces con
                <b>{n_cruces}</b> de {len(capas)} capas revisadas.</div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""<div class="resumen-ok">✅ El área de estudio
                (<b>{ha_area:,.1f} ha</b>) no presenta cruces con las
                {len(capas)} capas revisadas.</div>""",
                unsafe_allow_html=True,
            )

        st.subheader("Resultados de la revisión")
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Descargar resultados (CSV)",
            tabla.to_csv(index=False).encode("utf-8-sig"),
            file_name="revision_restricciones.csv",
            mime="text/csv",
        )

        st.subheader("Visor")
        st_folium(construir_mapa(area, capas, intersecciones),
                  use_container_width=True, height=560, returned_objects=[])

st.markdown(
    f"<hr><center style='color:{VERDE_OSCURO}'>VIAPRO Consultoría · Revisión cartográfica de restricciones ambientales</center>",
    unsafe_allow_html=True,
)
