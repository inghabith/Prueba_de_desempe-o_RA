"""
Extracción: lee cada fuente tal como viene, sin limpiarla.
La limpieza y las reglas de negocio están en transformacion.py.
"""
import logging
from pathlib import Path

import pandas as pd
import requests

from etl.config import ARCHIVO_CATALOGO_RESPALDO, ARCHIVOS

log = logging.getLogger(__name__)


def leer_csv_fuente(ruta_datos: str, fuente: str) -> pd.DataFrame:
    """Lee el CSV crudo de una fuente. Todo se lee como texto para no perder formatos."""
    ruta = Path(ruta_datos) / ARCHIVOS[fuente]
    df = pd.read_csv(ruta, dtype=str, encoding="latin-1")
    log.info("Fuente %s: %s filas leídas de %s", fuente, len(df), ruta)
    return df


def leer_catalogo(url_api: str, tamano_pagina: int, ruta_datos: str) -> pd.DataFrame:
    """
    Obtiene el catálogo de productos desde la API, recorriendo todas sus páginas.
    Si la API no responde, usa el archivo de respaldo con el mismo contenido,
    para que el pipeline funcione en ambos casos.
    """
    try:
        productos, pagina = [], 1
        while True:
            respuesta = requests.get(
                f"{url_api}/productos",
                params={"pagina": pagina, "tamano": tamano_pagina},
                timeout=10,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            productos.extend(datos["productos"])
            if pagina * tamano_pagina >= datos["total"]:
                break
            pagina += 1
        log.info("Catálogo obtenido de la API: %s productos", len(productos))
        return pd.DataFrame(productos)
    except requests.RequestException as error:
        log.warning("La API de productos no respondió (%s). Se usa el archivo de respaldo.", error)
        df = pd.read_csv(Path(ruta_datos) / ARCHIVO_CATALOGO_RESPALDO, dtype=str)
        df["activo"] = df["activo"] == "true"
        return df
