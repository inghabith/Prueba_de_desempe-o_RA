-- Pregunta 3b: ¿Cuáles son los 10 productos con mayor tasa de devolución?
-- Tasa = unidades devueltas / unidades vendidas. Solo se consideran productos con al menos
-- 100 unidades vendidas, para que un producto con 1 venta y 1 devolución no salga primero.
-- Solo se cuentan cancelaciones (las devoluciones del cliente), no ajustes de inventario.
WITH vendidas AS (
    SELECT codigo_producto, SUM(cantidad) AS unidades_vendidas
    FROM fact_ventas
    GROUP BY codigo_producto
),
devueltas AS (
    SELECT codigo_producto, SUM(cantidad_devuelta) AS unidades_devueltas
    FROM fact_devoluciones
    WHERE tipo = 'CANCELACION'
    GROUP BY codigo_producto
)
SELECT
    p.codigo_producto,
    p.nombre,
    v.unidades_vendidas,
    d.unidades_devueltas,
    ROUND(100.0 * d.unidades_devueltas / v.unidades_vendidas, 2) AS tasa_devolucion_pct
FROM vendidas v
JOIN devueltas d ON d.codigo_producto = v.codigo_producto
JOIN dim_producto p ON p.codigo_producto = v.codigo_producto
WHERE v.unidades_vendidas >= 100
ORDER BY tasa_devolucion_pct DESC
LIMIT 10;
