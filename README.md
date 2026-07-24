# Visor de restricciones ambientales · VIAPRO Consultoría

Aplicación web para revisar si un área de estudio (KMZ/KML) se cruza con las
capas ambientales de revisión. Las capas están **precargadas** en la app:
los usuarios solo suben el KMZ.

## Estructura
```
visor-viapro/
├── app.py                 # Aplicación Streamlit
├── convertir_capas.py     # Convierte sus shapefiles a GeoJSON
├── requirements.txt
├── assets/logo.jpg        # Logo VIAPRO
├── capas/                 # ← AQUÍ van las capas de revisión (GeoJSON/GPKG/SHP)
└── ejemplo_area_estudio.kmz  # KMZ de prueba (cruza con las capas DEMO)
```

## 1. Cargar sus capas reales
Las capas DEMO_*.geojson son solo de prueba: bórrelas cuando tenga las reales.
Convierta sus shapefiles con:
```bash
python convertir_capas.py C:/ruta/a/sus/shapefiles
```
El script reproyecta a WGS84, corrige geometrías y deja los GeoJSON en `capas/`.
El nombre del archivo es el nombre que verá el usuario (use nombres claros:
`RUNAP.geojson`, `Paramos.geojson`, `Reserva_Ley2.geojson`, etc.).

## 2. Ejecutar en local
```bash
pip install -r requirements.txt
streamlit run app.py
```
Abra http://localhost:8501 y pruebe con `ejemplo_area_estudio.kmz`.

## 3. Publicar gratis (Streamlit Community Cloud)
1. Suba esta carpeta a un repositorio de GitHub (puede ser privado).
2. Entre a https://share.streamlit.io con su cuenta de GitHub.
3. "New app" → elija el repositorio → archivo principal `app.py` → Deploy.
4. Comparta el enlace con su equipo. Para actualizar una capa, reemplace el
   archivo en `capas/` en GitHub y la app se redespliega sola.

> Nota: si el total de capas supera ~1 GB, considere GeoPackage por capa,
> simplificar geometrías o partir capas nacionales por departamento.

## Notas técnicas
- Áreas calculadas en EPSG:9377 (MAGNA-SIRGAS / Origen Nacional), en hectáreas.
- El visor acepta KMZ y KML; toma los polígonos del archivo.
- Resultados descargables en CSV.
