-- Repositorio analítico de DataMart.
-- PostgreSQL ejecuta este script automáticamente la primera vez que se crea la base.
-- Montos en libras esterlinas (GBP), moneda de ambas fuentes. Fechas en UTC.

-- Catálogo de productos (dimensión). Una fila por código normalizado.
CREATE TABLE IF NOT EXISTS dim_producto (
    codigo_producto  VARCHAR(20) PRIMARY KEY,
    nombre           TEXT        NOT NULL,   -- nombre canónico (descripción más frecuente)
    categoria        VARCHAR(30) NOT NULL,   -- viene de la API de productos
    pais_proveedor   VARCHAR(60),
    activo           BOOLEAN
);

-- Ventas válidas: una fila por línea de factura con cantidad mayor que cero.
CREATE TABLE IF NOT EXISTS fact_ventas (
    id_venta         BIGSERIAL PRIMARY KEY,
    factura          VARCHAR(20)   NOT NULL,
    codigo_producto  VARCHAR(20)   NOT NULL REFERENCES dim_producto (codigo_producto),
    descripcion_original TEXT,                -- descripción tal como venía en la fuente
    fecha_utc        TIMESTAMPTZ   NOT NULL,
    cantidad         INTEGER       NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(12,3) NOT NULL CHECK (precio_unitario > 0),
    revenue_bruto    NUMERIC(14,2) NOT NULL,  -- cantidad x precio unitario
    cliente_id       VARCHAR(20)   NOT NULL,  -- 'DESCONOCIDO' si la fuente no lo trae
    pais             VARCHAR(60)   NOT NULL,
    fuente           VARCHAR(30)   NOT NULL
);

-- Devoluciones y ajustes: líneas con cantidad menor o igual a cero, separadas de las ventas.
CREATE TABLE IF NOT EXISTS fact_devoluciones (
    id_devolucion     BIGSERIAL PRIMARY KEY,
    factura           VARCHAR(20)   NOT NULL,
    codigo_producto   VARCHAR(20)   NOT NULL REFERENCES dim_producto (codigo_producto),
    descripcion_original TEXT,
    fecha_utc         TIMESTAMPTZ   NOT NULL,
    tipo              VARCHAR(15)   NOT NULL,  -- CANCELACION (factura con C) o AJUSTE
    cantidad_devuelta INTEGER       NOT NULL CHECK (cantidad_devuelta >= 0),
    precio_unitario   NUMERIC(12,3) NOT NULL,
    monto_devuelto    NUMERIC(14,2) NOT NULL,  -- cantidad devuelta x precio unitario
    cliente_id        VARCHAR(20)   NOT NULL,
    pais              VARCHAR(60)   NOT NULL,
    fuente            VARCHAR(30)   NOT NULL
);

-- Revenue bruto y neto por producto y día (regla de negocio de la sección 5).
CREATE TABLE IF NOT EXISTS resumen_producto_diario (
    fecha              DATE          NOT NULL,
    codigo_producto    VARCHAR(20)   NOT NULL REFERENCES dim_producto (codigo_producto),
    unidades_vendidas  INTEGER       NOT NULL,
    revenue_bruto      NUMERIC(14,2) NOT NULL,
    unidades_devueltas INTEGER       NOT NULL,
    monto_devuelto     NUMERIC(14,2) NOT NULL,
    revenue_neto       NUMERIC(14,2) NOT NULL,  -- revenue bruto - monto devuelto
    PRIMARY KEY (fecha, codigo_producto)
);

-- Registros rechazados con su motivo y su fuente de origen.
CREATE TABLE IF NOT EXISTS log_rechazos (
    id_rechazo       BIGSERIAL PRIMARY KEY,
    fuente           VARCHAR(30)   NOT NULL,
    motivo           TEXT          NOT NULL,
    factura          VARCHAR(20),
    codigo_producto  VARCHAR(20),
    descripcion      TEXT,
    cantidad         INTEGER,
    fecha_utc        TIMESTAMPTZ,
    precio_unitario  NUMERIC(12,3),
    cliente_id       VARCHAR(20),
    pais             VARCHAR(60),
    fecha_proceso    DATE          NOT NULL   -- fecha lógica de la ejecución del DAG
);

-- Índices para las consultas de negocio más frecuentes.
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON fact_ventas (fecha_utc);
CREATE INDEX IF NOT EXISTS idx_ventas_producto ON fact_ventas (codigo_producto);
CREATE INDEX IF NOT EXISTS idx_devoluciones_producto ON fact_devoluciones (codigo_producto);
CREATE INDEX IF NOT EXISTS idx_rechazos_motivo ON log_rechazos (fuente, motivo);
