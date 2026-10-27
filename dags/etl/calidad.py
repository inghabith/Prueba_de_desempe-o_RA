"""
Validación de calidad: revisa las tablas transformadas antes de cargarlas.
Si alguna regla falla, la tarea falla y no se carga nada al repositorio analítico.
"""
import logging

log = logging.getLogger(__name__)


def validar(tablas: dict, filas_entrada: int) -> None:
    """Ejecuta todas las validaciones y lanza un error con la lista de las que fallaron."""
    ventas = tablas["fact_ventas"]
    devoluciones = tablas["fact_devoluciones"]
    productos = tablas["dim_producto"]
    resumen = tablas["resumen_producto_diario"]
    rechazos = tablas["log_rechazos"]

    filas_salida = len(ventas) + len(devoluciones) + len(rechazos)
    codigos_hechos = set(ventas["codigo_producto"]) | set(devoluciones["codigo_producto"])

    reglas = {
        # Ninguna fila se pierde: todo lo que entra termina como venta, devolución o rechazo.
        "Cuadre de filas (entrada = ventas + devoluciones + rechazos)": filas_entrada == filas_salida,
        "Hay ventas para cargar": len(ventas) > 0,
        "Ventas con cantidad mayor que cero": (ventas["cantidad"] > 0).all(),
        "Ventas con precio mayor que cero": (ventas["precio_unitario"] > 0).all(),
        "Devoluciones con cantidad no negativa": (devoluciones["cantidad_devuelta"] >= 0).all(),
        "Sin nulos en columnas clave": not ventas[["factura", "codigo_producto", "fecha_utc",
                                                   "cliente_id"]].isna().any().any(),
        "Todos los productos existen en dim_producto": codigos_hechos <= set(productos["codigo_producto"]),
        "Códigos de producto únicos en dim_producto": productos["codigo_producto"].is_unique,
        "Revenue neto = bruto - devoluciones": (
            (resumen["revenue_bruto"] - resumen["monto_devuelto"] - resumen["revenue_neto"]).abs() < 0.01
        ).all(),
        "Fechas en UTC": str(ventas["fecha_utc"].dt.tz) == "UTC",
    }

    for regla, cumple in reglas.items():
        log.info("%s %s", "OK   " if cumple else "FALLA", regla)

    fallidas = [regla for regla, cumple in reglas.items() if not cumple]
    if fallidas:
        raise ValueError(f"Validación de calidad fallida: {fallidas}")

    log.info("Resumen: %s ventas, %s devoluciones, %s rechazos, %s productos",
             len(ventas), len(devoluciones), len(rechazos), len(productos))
    log.info("Rechazos por motivo:\n%s", rechazos.groupby(["fuente", "motivo"]).size().to_string())
