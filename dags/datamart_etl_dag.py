"""
DAG del pipeline ETL de DataMart.

Este archivo solo orquesta: define las tareas, su orden y sus reintentos.
La lógica de cada etapa está en el paquete etl/:
  extraccion.py -> transformacion.py -> calidad.py -> carga.py

Las tareas se pasan los datos mediante archivos parquet en una carpeta temporal
(RUTA_STAGING), porque Airflow no está pensado para mover tablas grandes entre tareas.
"""
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pendulum
from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook

from etl import calidad, carga, extraccion, transformacion
from etl.config import FUENTE_DIARIA, FUENTE_HISTORICA, RUTA_STAGING

TABLAS = ["dim_producto", "fact_ventas", "fact_devoluciones", "resumen_producto_diario", "log_rechazos"]


def ruta_staging(nombre: str) -> str:
    """Ruta del archivo intermedio de una tarea."""
    Path(RUTA_STAGING).mkdir(parents=True, exist_ok=True)
    return f"{RUTA_STAGING}/{nombre}.parquet"


def leer_tablas() -> dict:
    """Lee las tablas transformadas que dejó la tarea transformar."""
    return {tabla: pd.read_parquet(ruta_staging(tabla)) for tabla in TABLAS}


@dag(
    dag_id="datamart_etl",
    description="Ventas de DataMart: CSV diario + histórico + API de productos -> repositorio analítico",
    schedule="@daily",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,         # solo se ejecuta el día más reciente, no los días pasados
    max_active_runs=1,     # nunca dos ejecuciones al tiempo sobre las mismas tablas
    default_args={
        "retries": 2,                         # reintentos automáticos ante fallos
        "retry_delay": timedelta(minutes=1),
    },
    tags=["datamart", "etl"],
)
def datamart_etl():

    @task
    def extraer_ventas_diarias() -> str:
        df = extraccion.leer_csv_fuente(Variable.get("ruta_datos"), FUENTE_DIARIA)
        df.to_parquet(ruta_staging(FUENTE_DIARIA))
        return ruta_staging(FUENTE_DIARIA)

    @task
    def extraer_historico() -> str:
        df = extraccion.leer_csv_fuente(Variable.get("ruta_datos"), FUENTE_HISTORICA)
        df.to_parquet(ruta_staging(FUENTE_HISTORICA))
        return ruta_staging(FUENTE_HISTORICA)

    @task
    def extraer_catalogo_api() -> str:
        api = BaseHook.get_connection("api_productos")
        df = extraccion.leer_catalogo(
            url_api=f"http://{api.host}:{api.port}",
            tamano_pagina=int(Variable.get("tamano_pagina_api")),
            ruta_datos=Variable.get("ruta_datos"),
        )
        df.to_parquet(ruta_staging("catalogo"))
        return ruta_staging("catalogo")

    @task
    def transformar(ruta_diaria: str, ruta_historica: str, ruta_catalogo: str) -> int:
        diaria = pd.read_parquet(ruta_diaria)
        historica = pd.read_parquet(ruta_historica)
        tablas = transformacion.transformar(
            diaria, historica, pd.read_parquet(ruta_catalogo),
            zona_horaria=Variable.get("zona_horaria_origen"),
        )
        for nombre, df in tablas.items():
            df.to_parquet(ruta_staging(nombre))
        # Se devuelve el total de filas de entrada para el cuadre en la validación.
        return len(diaria) + len(historica)

    @task
    def validar_calidad(filas_entrada: int) -> None:
        calidad.validar(leer_tablas(), filas_entrada)

    @task
    def cargar_repositorio(ds=None) -> None:
        conexion = PostgresHook(postgres_conn_id="dw_postgres").get_conn()
        carga.cargar(conexion, leer_tablas(), fecha_proceso=ds)

    # Dependencias: las tres extracciones corren en paralelo y luego el resto en orden.
    filas = transformar(extraer_ventas_diarias(), extraer_historico(), extraer_catalogo_api())
    validar_calidad(filas) >> cargar_repositorio()


datamart_etl()
