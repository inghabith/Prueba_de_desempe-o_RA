"""
Parámetros fijos del pipeline: nombres de archivos, mapeo de columnas por fuente
y textos de los motivos de rechazo. Los parámetros operativos que pueden cambiar
sin tocar código están en Airflow Variables (ver airflow/init_airflow.sh).
"""

# Identificadores de cada fuente (se guardan en las tablas y en el log de rechazos).
FUENTE_DIARIA = "ventas_diarias"
FUENTE_HISTORICA = "historico_ventas"

# Archivos crudos, relativos a la carpeta de datos (Variable ruta_datos).
ARCHIVOS = {
    FUENTE_DIARIA: "raw/ventas_diarias.csv.gz",       # data.csv de Kaggle (carrie1/ecommerce-data)
    FUENTE_HISTORICA: "raw/historico_ventas.csv.gz",  # Sales Transaction v.4a.csv de Kaggle
}
# Catálogo de respaldo: el mismo archivo que sirve la API, por si la API no responde.
ARCHIVO_CATALOGO_RESPALDO = "catalogo/productos.csv"

# Carpeta temporal donde cada tarea deja su resultado para la siguiente.
RUTA_STAGING = "/opt/airflow/staging"

# Cada fuente trae nombres de columna distintos. Aquí se traducen a un esquema común.
MAPEO_COLUMNAS = {
    FUENTE_DIARIA: {
        "InvoiceNo": "factura",
        "StockCode": "codigo_producto",
        "Description": "descripcion",
        "Quantity": "cantidad",
        "InvoiceDate": "fecha",
        "UnitPrice": "precio_unitario",
        "CustomerID": "cliente_id",
        "Country": "pais",
    },
    FUENTE_HISTORICA: {
        "TransactionNo": "factura",
        "ProductNo": "codigo_producto",
        "ProductName": "descripcion",
        "Quantity": "cantidad",
        "Date": "fecha",
        "Price": "precio_unitario",
        "CustomerNo": "cliente_id",
        "Country": "pais",
    },
}

# Formato de fecha de cada fuente: la diaria trae hora, la histórica solo el día.
FORMATO_FECHA = {
    FUENTE_DIARIA: "%m/%d/%Y %H:%M",
    FUENTE_HISTORICA: "%m/%d/%Y",
}

# Patrón de un código de producto del catálogo: 5 dígitos y, opcionalmente, letras
# (ej. 85123A). Códigos como POST, DOT, M o BANK CHARGES son cargos, no productos.
PATRON_CODIGO_PRODUCTO = r"^\d{5}[A-Z]*$"

# Valores por defecto cuando falta información.
CLIENTE_DESCONOCIDO = "DESCONOCIDO"
CATEGORIA_DESCONOCIDA = "Sin categoría"
NOMBRE_DESCONOCIDO = "SIN DESCRIPCIÓN"

# Motivos de rechazo (texto que queda en log_rechazos).
MOTIVO_DUPLICADO_EXACTO = "Registro duplicado exacto dentro de la misma fuente"
MOTIVO_DUPLICADO_FUENTES = "Duplicado de ventas_diarias (misma factura y producto)"
MOTIVO_FECHA_HISTORICO = "Fecha posterior al inicio de ventas_diarias: histórico inconsistente"
MOTIVO_CODIGO_INVALIDO = "Código no corresponde a un producto del catálogo"
MOTIVO_PRECIO_INVALIDO = "Precio unitario cero o negativo en una venta"

# Columnas del esquema común, en orden.
COLUMNAS_COMUNES = [
    "factura", "codigo_producto", "descripcion", "cantidad",
    "fecha_utc", "precio_unitario", "cliente_id", "pais", "fuente",
]
