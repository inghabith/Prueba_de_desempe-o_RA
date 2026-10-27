# Decisiones técnicas

Este documento explica cómo se diseñó el pipeline, cómo se resolvió cada caso ambiguo de los datos y cómo se
garantiza la idempotencia. La evidencia con números de cada hallazgo está en `notebooks/01_exploracion.ipynb`.

## 1. Arquitectura

```
 data/raw/ventas_diarias.csv.gz ──┐
 data/raw/historico_ventas.csv.gz ┼──> Airflow (DAG datamart_etl) ──> PostgreSQL datamart_dw
 API de productos (FastAPI) ──────┘         pandas                     (repositorio analítico)
```

| Servicio | Función |
|---|---|
| `postgres-airflow` | Base de metadatos de Airflow. Separada del repositorio analítico. |
| `postgres-dw` | Repositorio analítico. Sus tablas se crean al iniciar con `sql/ddl/01_crear_tablas.sql`. |
| `api-productos` | Simula el sistema legado del catálogo. Endpoints `/productos` (paginado) y `/productos/{codigo}`. |
| `airflow-init` | Crea la base de Airflow, el usuario admin, las Connections y las Variables, y termina. |
| `airflow-webserver` / `airflow-scheduler` | Interfaz web y ejecución del DAG (LocalExecutor). |
| `jupyter` | Notebooks de exploración y de consultas de negocio. |

**Configuración sin pasos manuales.** `docker-compose.yml` lee las variables sensibles de `.env.example` y, si
existe, de `.env` (que tiene prioridad y está en `.gitignore`). Así el entorno arranca con un solo comando y no
hay usuarios ni contraseñas escritos en el código.

**Airflow Connections** (creadas por `airflow/init_airflow.sh`):
- `dw_postgres`: repositorio analítico. La usa la tarea de carga.
- `api_productos`: API del catálogo. La usa la tarea de extracción del catálogo.

**Airflow Variables:**
- `ruta_datos`: carpeta de los archivos de entrada.
- `zona_horaria_origen`: zona horaria de las fechas de las fuentes (`Europe/London`), para convertirlas a UTC.
- `tamano_pagina_api`: cuántos productos se piden por página a la API.

## 2. El DAG

```
extraer_ventas_diarias ─┐
extraer_historico ──────┼─> transformar ─> validar_calidad ─> cargar_repositorio
extraer_catalogo_api ───┘
```

- Programación diaria (`@daily`), sin `catchup`, con una sola ejecución activa a la vez.
- 2 reintentos automáticos por tarea, con 1 minuto de espera.
- El DAG se activa al crearse, así que corre solo al levantar el entorno.
- El archivo del DAG solo orquesta. La lógica está separada por etapa en `dags/etl/`:
  `extraccion.py`, `transformacion.py`, `calidad.py` y `carga.py`. Las constantes van en `config.py`.
- Las tareas se pasan los datos con archivos parquet en una carpeta temporal, porque XCom no está pensado para
  mover tablas grandes.
- **Respaldo del catálogo:** si la API no responde, `extraer_catalogo_api` lee `data/catalogo/productos.csv`, que
  es el mismo archivo que sirve la API. El pipeline funciona en ambos casos.

**Validación de calidad** (`calidad.py`). Si alguna regla falla, la tarea falla y no se carga nada:
cuadre de filas (entrada = ventas + devoluciones + rechazos), ventas con cantidad y precio mayores que cero,
claves sin nulos, todos los productos de los hechos existen en `dim_producto`, códigos únicos en la dimensión,
revenue neto = bruto − devoluciones, y fechas en UTC.

## 3. Modelo del repositorio analítico

Diagrama: `docs/diagrama_modelo.png`. La versión para dbdiagram.io está en `docs/modelo_datos.dbml`.

| Tabla | Grano | Para qué sirve |
|---|---|---|
| `dim_producto` | un código de producto | Nombre canónico, categoría, país del proveedor y si está activo |
| `fact_ventas` | una línea de factura vendida | Ventas válidas con su revenue bruto |
| `fact_devoluciones` | una línea con cantidad ≤ 0 | Cancelaciones y ajustes, separados de las ventas |
| `resumen_producto_diario` | producto + día | Revenue bruto, monto devuelto y revenue neto |
| `log_rechazos` | un registro rechazado | Motivo, fuente y datos originales del registro |

**Por qué este diseño:**
- Es un modelo estrella simple: una dimensión de producto y dos tablas de hechos. Las preguntas de negocio
  agrupan sobre todo por producto y categoría, así que es la única dimensión que hace falta.
- **Ventas y devoluciones van en tablas separadas,** como exige la regla de negocio. Así ninguna consulta mezcla
  devoluciones con ventas por error, y el neto se calcula de forma explícita.
- `resumen_producto_diario` guarda el revenue neto, como pide la regla de negocio: bruto menos devoluciones del
  mismo producto en el mismo día. También simplifica las consultas mensuales y por producto.
- País y cliente son atributos de la transacción y se dejan en los hechos. Una dimensión de cliente solo tendría
  el ID, así que no aporta nada a estas preguntas.
- Las fechas se agrupan con `DATE_TRUNC`, así que no hace falta una dimensión de fecha.
- La descripción original se conserva en los hechos para poder auditar las inconsistencias (pregunta 6).

## 4. Reglas de negocio y cómo se aplican

| Regla | Implementación |
|---|---|
| Cantidad ≤ 0 es devolución o ajuste | Va a `fact_devoluciones`. Tipo `CANCELACION` si la factura empieza con "C", `AJUSTE` si no. |
| Venta con precio ≤ 0 | Rechazo con motivo en `log_rechazos`. |
| Fechas en UTC | Se interpretan como hora de `Europe/London` y se convierten a UTC (`convertir_a_utc`). |
| Códigos en mayúsculas y sin espacios | `normalizar_codigo`, antes de cualquier cruce con el catálogo. |
| Revenue bruto y neto | `revenue_bruto` = cantidad × precio. `revenue_neto` = bruto − devoluciones del mismo producto y día. |

**Otras reglas de limpieza encontradas en la exploración:**
- **Duplicados exactos dentro de una fuente:** se conserva la primera aparición y el resto va a rechazos.
- **Códigos que no son productos** (POST, DOT, M, C2, BANK CHARGES, AMAZONFEE, CRUK, GIFT_..., etc.): son
  envíos, comisiones, descuentos y ajustes contables. Todo código que no cumple el patrón del catálogo
  `5 dígitos + letras opcionales` (por ejemplo `85123A`) se rechaza.
- **Moneda:** ambas fuentes son de una tienda del Reino Unido, así que todos los montos quedan en libras
  esterlinas (GBP), sin conversión.

## 5. Casos ambiguos

### 5.1 Transacciones sin customer ID
135.080 líneas (24,9%) no tienen cliente.

**Decisión:** se incluyen con el cliente `DESCONOCIDO`.

**Impacto:** se conservan 1,5 millones de GBP en ventas que de otra forma desaparecerían de todos los reportes.
Las métricas por cliente deben filtrar `cliente_id <> 'DESCONOCIDO'`. La pregunta 5 muestra que estas facturas
son distintas: tienen más del doble de ticket promedio y unas 4 veces más líneas por factura. Parecen ventas
manuales o de mostrador.

### 5.2 Varias descripciones para un mismo código
645 códigos tienen más de una descripción. Además de las variaciones de mayúsculas y espacios, hay notas del
almacén escritas en ese campo ("check", "damages", "wet pallet").

**Decisión:** se normaliza cada descripción (mayúsculas, sin espacios sobrantes), y el nombre canónico es la que
más se repite para ese código. En caso de empate, la primera en orden alfabético. Las notas del almacén aparecen
pocas veces, así que nunca ganan (`nombre_canonico`).

### 5.3 Duplicados entre las dos fuentes
Al comparar las fuentes se encontró que el histórico (`Sales Transaction v.4a.csv`) **no** contiene años
adicionales. Tiene las mismas facturas de la fuente diaria (23.190 de 23.204, con el mismo producto, cantidad y
cliente), pero con todas las fechas corridas exactamente 2.922 días (8 años) y los precios alterados (por ejemplo,
2,55 → 12,86).

**Decisión:**
1. Una línea del histórico es duplicada si tiene **la misma factura y el mismo código de producto** que una línea
   de la fuente diaria. No se usan la fecha ni el precio, porque el histórico los trae alterados.
   **Gana la fuente diaria**, que es la operacional. Resultado: 529.450 líneas rechazadas.
2. Las 1.700 líneas restantes tienen fechas de 2019, posteriores a la fuente diaria. Un histórico debe ser
   anterior, así que se rechazan por "fecha inconsistente". Cargarlas como ventas nuevas habría creado ventas
   aisladas 8 años después del resto de los datos, con precios inflados.

Ningún registro se pierde sin explicación: todos quedan en `log_rechazos` con su motivo.

**Otra fuente evaluada:** también se revisó `online_retail.csv` (Kaggle `thedevastator/online-retail-transaction-dataset`).
Se descartó porque es una copia exacta de `data.csv`: las mismas 541.909 filas y fechas, con una columna `index`
extra y los IDs en formato decimal. No permitía mostrar la unificación de columnas y formatos que describe el
enunciado.

### 5.4 Categoría de los productos
Los datasets no traen categoría. La API de productos sirve `data/catalogo/productos.csv`, generado con
`scripts/generar_catalogo.py`:
- **Categoría:** por palabras clave en el nombre canónico (por ejemplo, "CARD" o "PAPER" → Papelería; "BAG" o
  "NECKLACE" → Ropa; "BALL" o "GAME" → Deportes; "LED" o "CLOCK" → Electrónica). Lo que no coincide queda en
  Hogar, que es el grueso del catálogo de esta tienda.
- **País del proveedor:** los datos no lo traen. Se asume "Reino Unido".
- **Activo:** un producto está activo si se vendió en los últimos 90 días del periodo.

Los códigos que aparecen en las transacciones pero no en el catálogo quedan con categoría "Sin categoría".

## 6. Idempotencia

- La carga (`carga.py`) vacía las cinco tablas y las vuelve a llenar **dentro de una sola transacción**. Si algo
  falla, se hace rollback y las tablas quedan como estaban.
- La transformación es determinista: los mismos archivos producen las mismas filas, en el mismo orden.
- `fecha_proceso` en `log_rechazos` es la fecha lógica del DAG (`ds`), no la hora actual.
- `RESTART IDENTITY` reinicia los IDs, así que también coinciden entre ejecuciones.

**Verificación:** se ejecutó el DAG dos veces para el mismo día y se comparó un hash MD5 del contenido de cada
tabla. Los cinco hashes fueron idénticos.

## 7. Resultado de la carga

| | Filas |
|---|---|
| Entrada (ventas diarias + histórico) | 1.078.259 |
| `fact_ventas` | 522.504 |
| `fact_devoluciones` | 9.992 |
| `log_rechazos` | 545.763 |
| `dim_producto` | 3.911 |
| `resumen_producto_diario` | 277.914 |

| Fuente | Motivo de rechazo | Filas |
|---|---|---|
| historico_ventas | Duplicado de ventas_diarias (misma factura y producto) | 529.450 |
| historico_ventas | Registro duplicado exacto dentro de la misma fuente | 5.200 |
| historico_ventas | Fecha posterior al inicio de ventas_diarias | 1.700 |
| ventas_diarias | Registro duplicado exacto dentro de la misma fuente | 5.268 |
| ventas_diarias | Código no corresponde a un producto del catálogo | 2.989 |
| ventas_diarias | Precio unitario cero o negativo en una venta | 1.156 |

## 8. Pendientes y mejoras posibles

- **Carga incremental:** hoy cada ejecución recarga todo, que es simple y claramente idempotente. Con volúmenes
  mayores convendría cargar solo el día de la ejecución, reemplazando por rango de fechas.
- **Catálogo real:** la categoría por palabras clave es una aproximación. Con el sistema legado real, la API
  devolvería la categoría oficial y el pipeline no cambiaría.
- **Alertas:** se podría avisar por correo cuando falle la validación de calidad.
