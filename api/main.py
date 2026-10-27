"""
API interna de productos de DataMart.

Simula el sistema legado que mantiene el catálogo. Lee el catálogo desde
catalogo/productos.csv y expone dos endpoints:
  - GET /productos?pagina=1&tamano=100  -> listado paginado
  - GET /productos/{codigo}             -> un producto por su código
"""
import csv
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

RUTA_CATALOGO = Path(__file__).parent / "catalogo" / "productos.csv"

app = FastAPI(title="API de productos DataMart")


def cargar_catalogo() -> dict:
    """Lee el CSV del catálogo y lo devuelve como diccionario {codigo: producto}."""
    with open(RUTA_CATALOGO, encoding="utf-8") as archivo:
        filas = csv.DictReader(archivo)
        return {
            fila["codigo"]: {
                "codigo": fila["codigo"],
                "nombre": fila["nombre"],
                "categoria": fila["categoria"],
                "pais_proveedor": fila["pais_proveedor"],
                "activo": fila["activo"] == "true",
            }
            for fila in filas
        }


# El catálogo se carga una sola vez al iniciar la API.
CATALOGO = cargar_catalogo()


@app.get("/productos")
def listar_productos(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(100, ge=1, le=1000),
):
    """Devuelve una página del catálogo y el total de productos."""
    productos = list(CATALOGO.values())
    inicio = (pagina - 1) * tamano
    return {
        "pagina": pagina,
        "tamano": tamano,
        "total": len(productos),
        "productos": productos[inicio:inicio + tamano],
    }


@app.get("/productos/{codigo}")
def obtener_producto(codigo: str):
    """Devuelve un producto por su código (se normaliza a mayúsculas y sin espacios)."""
    codigo_normalizado = codigo.upper().replace(" ", "")
    producto = CATALOGO.get(codigo_normalizado)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto
