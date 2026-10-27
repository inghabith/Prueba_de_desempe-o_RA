-- Pregunta 7: recomendación para el equipo de producto, respaldada con números.
-- Hallazgo: unas pocas cancelaciones de pedidos gigantes concentran gran parte del dinero
-- devuelto. Esta consulta muestra las 10 cancelaciones más grandes y su peso en el total.
WITH total AS (
    SELECT SUM(monto_devuelto) AS monto_total
    FROM fact_devoluciones
    WHERE tipo = 'CANCELACION'
)
SELECT
    d.factura,
    d.fecha_utc::DATE                                         AS fecha,
    d.codigo_producto,
    p.nombre,
    d.cantidad_devuelta,
    d.monto_devuelto,
    ROUND(100 * d.monto_devuelto / t.monto_total, 2)          AS pct_del_total_devuelto,
    ROUND(100 * SUM(d.monto_devuelto) OVER (ORDER BY d.monto_devuelto DESC)
          / t.monto_total, 2)                                 AS pct_acumulado
FROM fact_devoluciones d
JOIN dim_producto p ON p.codigo_producto = d.codigo_producto
CROSS JOIN total t
WHERE d.tipo = 'CANCELACION'
ORDER BY d.monto_devuelto DESC
LIMIT 10;
