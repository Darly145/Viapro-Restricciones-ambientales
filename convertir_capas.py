# -*- coding: utf-8 -*-
"""
Convierte una carpeta de shapefiles a GeoJSON listos para el visor.
Uso:  python convertir_capas.py C:/ruta/a/mis/shapefiles
Los archivos convertidos quedan en la carpeta ./capas de la app.
"""
import sys
from pathlib import Path

import geopandas as gpd

DESTINO = Path(__file__).parent / "capas"


def convertir(carpeta_shp: str):
    DESTINO.mkdir(exist_ok=True)
    shps = sorted(Path(carpeta_shp).rglob("*.shp"))
    if not shps:
        print("No se encontraron shapefiles en", carpeta_shp)
        return
    for shp in shps:
        try:
            gdf = gpd.read_file(shp)
            if gdf.crs is None:
                print(f"⚠️  {shp.name}: sin CRS definido, se asume EPSG:4326")
                gdf = gdf.set_crs(4326)
            gdf = gdf.to_crs(4326)
            gdf["geometry"] = gdf.geometry.make_valid()
            gdf = gdf[~gdf.geometry.is_empty]
            # Simplificación ligera (~5 m) para aligerar el visor; ajústela o coméntela
            gdf["geometry"] = gdf.geometry.simplify(0.00005, preserve_topology=True)
            salida = DESTINO / f"{shp.stem}.geojson"
            gdf.to_file(salida, driver="GeoJSON")
            print(f"✅ {shp.name} → capas/{salida.name} ({len(gdf)} entidades)")
        except Exception as e:
            print(f"❌ Error con {shp.name}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        convertir(sys.argv[1])
