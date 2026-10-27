"""
Genera data/catalogo/productos.csv, el catálogo que sirve la API de productos.

Los datasets de Kaggle no traen catálogo, así que este script lo construye una sola vez
a partir de los códigos que aparecen en la fuente diaria. El archivo generado ya está en
el repositorio; este script se incluye para que se vea cómo se obtuvo cada campo.

Uso (desde la raíz del proyecto):  python scripts/generar_catalogo.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "dags"))

from etl.config import PATRON_CODIGO_PRODUCTO  # noqa: E402
from etl.transformacion import nombre_canonico, normalizar_codigo, normalizar_texto  # noqa: E402

# Supuesto: un producto está activo si se vendió en los últimos 90 días del periodo.
DIAS_PRODUCTO_ACTIVO = 90

# Supuesto: los datos no traen proveedor; la tienda es del Reino Unido.
PAIS_PROVEEDOR = "Reino Unido"

# Categorías por palabras clave en el nombre. Se revisan en este orden y gana la primera
# que coincida; si ninguna coincide, el producto queda en Hogar, que es el grueso del catálogo.
REGLAS_CATEGORIA = [
    ("Electrónica", ["LED", "CLOCK", "RADIO", "TORCH", "BATTERY", "CALCULATOR", "LAMP",
                     "PHONE", "ALARM", "ELECTRIC", "DIGITAL", "USB"]),
    ("Deportes", ["BALL", "GAME", "GAMES", "SKIPPING", "FRISBEE", "SPORT", "SPORTS", "PLAYING",
                  "JIGSAW", "DOMINOES", "KITE", "CRICKET", "FOOTBALL", "TENNIS", "BADMINTON"]),
    ("Papelería", ["CARD", "CARDS", "PAPER", "NOTEBOOK", "PENCIL", "PENCILS", "PEN", "PENS",
                   "WRAP", "STICKER", "STICKERS", "ENVELOPE", "ENVELOPES", "NOTEPAD", "CALENDAR",
                   "DIARY", "BOOK", "TAPE", "ERASER", "CHALK", "CRAYONS", "RIBBON", "RIBBONS"]),
    ("Ropa", ["BAG", "BAGS", "NECKLACE", "EARRINGS", "BRACELET", "SCARF", "GLOVES", "HAT",
              "SOCKS", "APRON", "SLIPPERS", "PURSE", "HAIR", "UMBRELLA"]),
]
CATEGORIA_POR_DEFECTO = "Hogar"


def asignar_categoria(nombre: str) -> str:
    """Devuelve la primera categoría cuya palabra clave aparece como palabra completa."""
    for categoria, palabras in REGLAS_CATEGORIA:
        if any(re.search(rf"\b{palabra}\b", nombre) for palabra in palabras):
            return categoria
    return CATEGORIA_POR_DEFECTO


def main() -> None:
    ventas = pd.read_csv(RAIZ / "data/raw/ventas_diarias.csv.gz", dtype=str, encoding="latin-1")
    lineas = pd.DataFrame({
        "codigo_producto": normalizar_codigo(ventas["StockCode"]),
        "descripcion": normalizar_texto(ventas["Description"]),
        "fecha": pd.to_datetime(ventas["InvoiceDate"], format="%m/%d/%Y %H:%M"),
    })
    lineas = lineas[lineas["codigo_producto"].str.match(PATRON_CODIGO_PRODUCTO)]

    nombres = nombre_canonico(lineas)
    ultima_venta = lineas.groupby("codigo_producto")["fecha"].max()
    corte_activo = lineas["fecha"].max() - pd.Timedelta(days=DIAS_PRODUCTO_ACTIVO)

    catalogo = pd.DataFrame({"codigo": nombres.index, "nombre": nombres.values})
    catalogo["categoria"] = catalogo["nombre"].map(asignar_categoria)
    catalogo["pais_proveedor"] = PAIS_PROVEEDOR
    catalogo["activo"] = (catalogo["codigo"].map(ultima_venta) >= corte_activo).map(
        {True: "true", False: "false"})

    destino = RAIZ / "data/catalogo/productos.csv"
    catalogo.to_csv(destino, index=False)
    print(f"Catálogo generado en {destino}: {len(catalogo)} productos")
    print(catalogo["categoria"].value_counts().to_string())


if __name__ == "__main__":
    main()
