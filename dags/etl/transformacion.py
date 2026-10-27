"""
Transformación: aquí se aplican todas las reglas de limpieza y de negocio.

Flujo general (función transformar):
  1. Estandarizar cada fuente al esquema común (columnas, tipos, códigos, fechas UTC).
  2. Rechazar duplicados exactos dentro de cada fuente.
  3. Rechazar del histórico lo que ya existe en la fuente diaria o tiene fechas inconsistentes.
  4. Rechazar códigos que no son productos.
  5. Separar ventas (cantidad > 0) de devoluciones y ajustes (cantidad <= 0).
  6. Rechazar ventas con precio cero o negativo.
  7. Construir las tablas finales del repositorio analítico.

Cada rechazo se guarda con su motivo y su fuente para la tabla log_rechazos.
"""
import pandas as pd

from etl.config import (
    CATEGORIA_DESCONOCIDA,
    CLIENTE_DESCONOCIDO,
    COLUMNAS_COMUNES,
    FORMATO_FECHA,
    FUENTE_DIARIA,
    FUENTE_HISTORICA,
    MAPEO_COLUMNAS,
    MOTIVO_CODIGO_INVALIDO,
    MOTIVO_DUPLICADO_EXACTO,
    MOTIVO_DUPLICADO_FUENTES,
    MOTIVO_FECHA_HISTORICO,
    MOTIVO_PRECIO_INVALIDO,
    NOMBRE_DESCONOCIDO,
    PATRON_CODIGO_PRODUCTO,
)


# ---------------------------------------------------------------------------
# Funciones de normalización
# ---------------------------------------------------------------------------

def normalizar_codigo(codigos: pd.Series) -> pd.Series:
    """Regla de negocio: códigos en mayúsculas y sin espacios."""
    return codigos.str.upper().str.replace(r"\s+", "", regex=True)


def normalizar_texto(textos: pd.Series) -> pd.Series:
    """Descripciones en mayúsculas, sin espacios al inicio o al final ni espacios dobles."""
    return textos.str.upper().str.strip().str.replace(r"\s+", " ", regex=True)


def convertir_a_utc(fechas: pd.Series, formato: str, zona_horaria: str) -> pd.Series:
    """Regla de negocio: las fechas vienen en hora local de la tienda y se guardan en UTC."""
    fechas_locales = pd.to_datetime(fechas, format=formato)
    return fechas_locales.dt.tz_localize(zona_horaria).dt.tz_convert("UTC")


def estandarizar_fuente(df: pd.DataFrame, fuente: str, zona_horaria: str) -> pd.DataFrame:
    """Lleva una fuente cruda al esquema común: mismos nombres de columna y tipos."""
    mapeo = MAPEO_COLUMNAS[fuente]
    # Solo se conservan las columnas mapeadas (por ejemplo, se descarta una columna "index").
    df = df[list(mapeo)].rename(columns=mapeo)

    df["factura"] = df["factura"].str.strip()
    df["codigo_producto"] = normalizar_codigo(df["codigo_producto"])
    # La descripción se conserva tal como viene para poder medir sus inconsistencias;
    # el nombre canónico normalizado se calcula al construir dim_producto.
    df["descripcion"] = df["descripcion"].str.strip()
    df["cantidad"] = pd.to_numeric(df["cantidad"]).astype(int)
    df["precio_unitario"] = pd.to_numeric(df["precio_unitario"])
    # Algunas fuentes traen el cliente como decimal ("17850.0"); se deja como texto entero.
    df["cliente_id"] = df["cliente_id"].str.replace(r"\.0$", "", regex=True)
    df["pais"] = df["pais"].str.strip()
    df["fecha_utc"] = convertir_a_utc(df.pop("fecha"), FORMATO_FECHA[fuente], zona_horaria)
    df["fuente"] = fuente
    return df[COLUMNAS_COMUNES]


# ---------------------------------------------------------------------------
# Manejo de rechazos
# ---------------------------------------------------------------------------

def separar(df: pd.DataFrame, rechazar: pd.Series, motivo: str, rechazos: list) -> pd.DataFrame:
    """
    Quita del DataFrame las filas marcadas en 'rechazar', las agrega a la lista
    de rechazos con su motivo y devuelve solo las filas que siguen siendo válidas.
    """
    rechazos.append(df[rechazar].assign(motivo=motivo))
    return df[~rechazar]


# ---------------------------------------------------------------------------
# Construcción de tablas
# ---------------------------------------------------------------------------

def nombre_canonico(lineas: pd.DataFrame) -> pd.Series:
    """
    Caso ambiguo: un mismo código con varias descripciones.
    Decisión: se normaliza cada descripción (mayúsculas, sin espacios sobrantes) y el
    nombre canónico es la que más se repite para ese código. Si hay empate, se toma la
    primera en orden alfabético.
    """
    conteo = (
        lineas.dropna(subset=["descripcion"])
        .assign(descripcion=lambda df: normalizar_texto(df["descripcion"]))
        .groupby(["codigo_producto", "descripcion"]).size()
        .reset_index(name="veces")
        .sort_values(["codigo_producto", "veces", "descripcion"], ascending=[True, False, True])
    )
    return conteo.drop_duplicates("codigo_producto").set_index("codigo_producto")["descripcion"]


def construir_dim_producto(ventas: pd.DataFrame, devoluciones: pd.DataFrame,
                           catalogo: pd.DataFrame) -> pd.DataFrame:
    """Un registro por código de producto, con nombre canónico y datos del catálogo (API)."""
    lineas = pd.concat([ventas, devoluciones])
    dim = pd.DataFrame({"codigo_producto": sorted(lineas["codigo_producto"].unique())})
    dim["nombre"] = dim["codigo_producto"].map(nombre_canonico(lineas)).fillna(NOMBRE_DESCONOCIDO)

    # Enriquecimiento con el catálogo. El código se normaliza antes de cruzar.
    catalogo = catalogo.assign(codigo=normalizar_codigo(catalogo["codigo"])).set_index("codigo")
    dim["categoria"] = dim["codigo_producto"].map(catalogo["categoria"]).fillna(CATEGORIA_DESCONOCIDA)
    dim["pais_proveedor"] = dim["codigo_producto"].map(catalogo["pais_proveedor"])
    dim["activo"] = dim["codigo_producto"].map(catalogo["activo"])
    return dim


def construir_resumen_diario(ventas: pd.DataFrame, devoluciones: pd.DataFrame) -> pd.DataFrame:
    """
    Regla de negocio: revenue neto = revenue bruto menos las devoluciones del mismo
    código de producto en el mismo día (UTC).
    """
    ventas_dia = (
        ventas.assign(fecha=ventas["fecha_utc"].dt.date)
        .groupby(["fecha", "codigo_producto"])
        .agg(unidades_vendidas=("cantidad", "sum"), revenue_bruto=("revenue_bruto", "sum"))
    )
    devoluciones_dia = (
        devoluciones.assign(fecha=devoluciones["fecha_utc"].dt.date)
        .groupby(["fecha", "codigo_producto"])
        .agg(unidades_devueltas=("cantidad_devuelta", "sum"), monto_devuelto=("monto_devuelto", "sum"))
    )
    resumen = ventas_dia.join(devoluciones_dia, how="outer").fillna(0).reset_index()
    resumen["revenue_neto"] = (resumen["revenue_bruto"] - resumen["monto_devuelto"]).round(2)
    resumen[["unidades_vendidas", "unidades_devueltas"]] = (
        resumen[["unidades_vendidas", "unidades_devueltas"]].astype(int)
    )
    return resumen


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def transformar(diaria_cruda: pd.DataFrame, historica_cruda: pd.DataFrame,
                catalogo: pd.DataFrame, zona_horaria: str) -> dict:
    """Aplica todas las reglas y devuelve las tablas listas para cargar."""
    rechazos = []

    # 1. Esquema común.
    diaria = estandarizar_fuente(diaria_cruda, FUENTE_DIARIA, zona_horaria)
    historica = estandarizar_fuente(historica_cruda, FUENTE_HISTORICA, zona_horaria)

    # 2. Duplicados exactos dentro de cada fuente: se conserva la primera aparición.
    diaria = separar(diaria, diaria.duplicated(), MOTIVO_DUPLICADO_EXACTO, rechazos)
    historica = separar(historica, historica.duplicated(), MOTIVO_DUPLICADO_EXACTO, rechazos)

    # 3. Caso ambiguo: duplicados entre fuentes.
    # Decisión: una línea del histórico es el mismo registro si tiene la misma factura y
    # el mismo código de producto que una línea de la fuente diaria. No se comparan fecha
    # ni precio porque el histórico los trae alterados. Gana la fuente diaria (operacional).
    claves_diaria = pd.MultiIndex.from_frame(diaria[["factura", "codigo_producto"]])
    claves_historica = pd.MultiIndex.from_frame(historica[["factura", "codigo_producto"]])
    historica = separar(historica, claves_historica.isin(claves_diaria),
                        MOTIVO_DUPLICADO_FUENTES, rechazos)

    # El histórico debe ser anterior a la fuente diaria; una fecha posterior es inconsistente.
    inicio_diaria = diaria["fecha_utc"].min()
    historica = separar(historica, historica["fecha_utc"] >= inicio_diaria,
                        MOTIVO_FECHA_HISTORICO, rechazos)

    # 4. Códigos que no siguen el patrón del catálogo (POST, DOT, M, BANK CHARGES...).
    lineas = pd.concat([diaria, historica], ignore_index=True)
    lineas = separar(lineas, ~lineas["codigo_producto"].str.match(PATRON_CODIGO_PRODUCTO),
                     MOTIVO_CODIGO_INVALIDO, rechazos)

    # 5. Regla de negocio: cantidad <= 0 es devolución o ajuste, no venta.
    es_devolucion = lineas["cantidad"] <= 0
    devoluciones = lineas[es_devolucion].copy()
    ventas = lineas[~es_devolucion]

    # 6. Regla de negocio: una venta válida no puede tener precio cero o negativo.
    ventas = separar(ventas, ventas["precio_unitario"] <= 0, MOTIVO_PRECIO_INVALIDO, rechazos).copy()

    # Caso ambiguo: transacciones sin customer ID.
    # Decisión: se incluyen en el análisis con un cliente genérico, para no perder su revenue.
    ventas["cliente_id"] = ventas["cliente_id"].fillna(CLIENTE_DESCONOCIDO)
    devoluciones["cliente_id"] = devoluciones["cliente_id"].fillna(CLIENTE_DESCONOCIDO)

    # 7. Tablas finales.
    ventas["revenue_bruto"] = (ventas["cantidad"] * ventas["precio_unitario"]).round(2)

    # Las facturas que empiezan con "C" son cancelaciones; el resto son ajustes de inventario.
    devoluciones["tipo"] = devoluciones["factura"].str.startswith("C").map(
        {True: "CANCELACION", False: "AJUSTE"})
    devoluciones["cantidad_devuelta"] = -devoluciones.pop("cantidad")
    devoluciones["monto_devuelto"] = (
        devoluciones["cantidad_devuelta"] * devoluciones["precio_unitario"]).round(2)

    return {
        "dim_producto": construir_dim_producto(ventas, devoluciones, catalogo),
        "fact_ventas": ventas.rename(columns={"descripcion": "descripcion_original"}),
        "fact_devoluciones": devoluciones.rename(columns={"descripcion": "descripcion_original"}),
        "resumen_producto_diario": construir_resumen_diario(ventas, devoluciones),
        "log_rechazos": pd.concat(rechazos, ignore_index=True),
    }
