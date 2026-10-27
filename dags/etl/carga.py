"""
Carga: escribe las tablas en el repositorio analítico (PostgreSQL).

Idempotencia: en una sola transacción se vacían las tablas y se vuelven a llenar.
Si el DAG se ejecuta dos veces con los mismos datos, el resultado es idéntico,
y si algo falla a mitad de la carga, la transacción se deshace y no queda nada a medias.
"""
import io
import logging

import pandas as pd

log = logging.getLogger(__name__)

# Orden de carga: primero la dimensión, porque los hechos la referencian.
ORDEN_CARGA = [
    "dim_producto",
    "fact_ventas",
    "fact_devoluciones",
    "resumen_producto_diario",
    "log_rechazos",
]


def copiar_tabla(cursor, tabla: str, df: pd.DataFrame) -> None:
    """Inserta un DataFrame con COPY de PostgreSQL, mucho más rápido que fila por fila."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    columnas = ", ".join(df.columns)
    cursor.copy_expert(f"COPY {tabla} ({columnas}) FROM STDIN WITH (FORMAT csv)", buffer)
    log.info("Tabla %s: %s filas cargadas", tabla, len(df))


def cargar(conexion, tablas: dict, fecha_proceso: str) -> None:
    """Reemplaza el contenido de todas las tablas dentro de una única transacción."""
    # La fecha de proceso es la fecha lógica del DAG (no la hora actual), para que
    # dos ejecuciones del mismo día produzcan exactamente los mismos datos.
    tablas["log_rechazos"] = tablas["log_rechazos"].assign(fecha_proceso=fecha_proceso)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"TRUNCATE {', '.join(ORDEN_CARGA)} RESTART IDENTITY")
            for tabla in ORDEN_CARGA:
                copiar_tabla(cursor, tabla, tablas[tabla])
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
