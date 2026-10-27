# Pipeline ETL DataMart con Apache Airflow

Pipeline que lleva las ventas de DataMart S.A.S. desde dos archivos CSV y una API de productos hasta un
repositorio analítico en PostgreSQL, orquestado con Apache Airflow y todo dentro de Docker.

- Decisiones técnicas y casos ambiguos: [docs/decisiones_tecnicas.md](docs/decisiones_tecnicas.md)
- Diagrama del modelo de datos: [docs/diagrama_modelo.png](docs/diagrama_modelo.png)
- Exploración de los datos: [notebooks/01_exploracion.ipynb](notebooks/01_exploracion.ipynb)
- Consultas de negocio: [sql/consultas/](sql/consultas/) y [notebooks/02_consultas_negocio.ipynb](notebooks/02_consultas_negocio.ipynb)

## Requisitos

- Docker con Docker Compose 2.24 o superior (Docker Desktop actual ya lo incluye).
- Los puertos 8080, 8888 y 8000 libres.

No hace falta instalar nada más: Python, pandas, Airflow, PostgreSQL y Jupyter corren dentro de los contenedores.

## Cómo levantarlo

```bash
git clone https://github.com/inghabith/Prueba_de_desempe-o_RA.git
cd Prueba_de_desempe-o_RA
docker compose up -d
```

Con eso basta. No hay que copiar el `.env`: el compose usa `.env.example` y, si existe un `.env`, toma sus
valores primero. La primera vez tarda unos minutos mientras descarga las imágenes.

Al iniciar, de forma automática:
1. Se crean las dos bases PostgreSQL (metadatos de Airflow y repositorio analítico) y las tablas del repositorio.
2. `airflow-init` crea el usuario administrador, las Connections y las Variables, y termina.
3. El scheduler detecta el DAG `datamart_etl`, que ya está activo, y lo ejecuta. Tarda alrededor de 1 minuto.

| Servicio | Dirección | Acceso |
|---|---|---|
| Airflow | http://localhost:8080 | usuario `admin`, contraseña `admin` |
| Jupyter | http://localhost:8888 | sin contraseña |
| API de productos | http://localhost:8000/docs | sin contraseña |

## Cómo verificar que funcionó

1. **El DAG corrió:** en http://localhost:8080 entra al DAG `datamart_etl`. La ejecución y sus 6 tareas deben
   estar en verde (success).
2. **Connections:** en *Admin → Connections* deben aparecer `dw_postgres` (PostgreSQL) y `api_productos` (HTTP).
3. **Variables:** en *Admin → Variables* deben aparecer `ruta_datos`, `zona_horaria_origen` y `tamano_pagina_api`.
4. **Los datos llegaron:** en http://localhost:8888 abre `notebooks/02_consultas_negocio.ipynb` y ejecútalo
   (*Run → Run All Cells*). Muestra el resultado de las consultas de cada pregunta de negocio sobre el repositorio
   analítico.
5. **La API responde:** en http://localhost:8000/docs prueba `GET /productos` y `GET /productos/85123A`.

Si prefieres la terminal, estos comandos hacen las mismas verificaciones:

```bash
docker compose exec airflow-scheduler airflow dags list-runs -d datamart_etl
docker compose exec airflow-scheduler airflow connections list
docker compose exec airflow-scheduler airflow variables list
docker compose exec postgres-dw psql -U datamart -d datamart_dw -c "SELECT COUNT(*) FROM fact_ventas;"
```

Resultado esperado: 522.504 ventas, 9.992 devoluciones, 545.763 rechazos y 3.911 productos.

## Estructura del proyecto

```
docker-compose.yml          servicios del entorno
.env.example                variables de entorno (el .env real está en .gitignore)
airflow/init_airflow.sh     crea el usuario admin, las Connections y las Variables al iniciar
api/                        API de productos (FastAPI)
jupyter/Dockerfile          imagen de Jupyter con pandas
dags/
  datamart_etl_dag.py       el DAG: solo define las tareas y su orden
  etl/
    config.py               mapeo de columnas, formatos de fecha y motivos de rechazo
    extraccion.py           lectura de los CSV y de la API
    transformacion.py       limpieza y reglas de negocio con pandas
    calidad.py              validaciones antes de cargar
    carga.py                carga idempotente a PostgreSQL
data/
  raw/                      los dos CSV de Kaggle, comprimidos
  catalogo/productos.csv    catálogo que sirve la API (y respaldo si la API no responde)
scripts/generar_catalogo.py cómo se generó el catálogo
sql/
  ddl/01_crear_tablas.sql   tablas del repositorio analítico (se ejecuta al iniciar)
  consultas/                una consulta por cada pregunta de negocio
notebooks/
  01_exploracion.ipynb      exploración de las fuentes y decisiones de calidad
  02_consultas_negocio.ipynb resultados de las preguntas de negocio
docs/
  decisiones_tecnicas.md    diseño, casos ambiguos e idempotencia
  diagrama_modelo.png       diagrama del modelo de datos
  modelo_datos.dbml         el mismo modelo para pegar en dbdiagram.io
```

## Fuentes de datos

| Archivo en el repo | Origen |
|---|---|
| `data/raw/ventas_diarias.csv.gz` | Kaggle `carrie1/ecommerce-data`, archivo `data.csv` (volcado diario) |
| `data/raw/historico_ventas.csv.gz` | Kaggle, archivo `Sales Transaction v.4a.csv` (historial) |

Los archivos están comprimidos con gzip para que el repositorio sea liviano; pandas los lee directamente.

## Volver a ejecutar o empezar de cero

- **Ejecutar el DAG otra vez:** botón *Trigger DAG* en la interfaz de Airflow. Como el DAG es idempotente,
  las tablas quedan con los mismos datos; solo cambia `fecha_proceso` en `log_rechazos` si la ejecución
  corresponde a otro día.
- **Borrar todo y empezar de cero:** `docker compose down -v` y luego `docker compose up -d`.
