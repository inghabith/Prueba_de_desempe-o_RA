-- Pregunta 2: ¿Qué categorías generaron más revenue bruto y cuáles tuvieron mayor proporción de devoluciones?
-- La proporción de devoluciones se mide en dinero: monto devuelto / revenue bruto.
SELECT
    p.categoria,
    SUM(r.revenue_bruto)                                          AS revenue_bruto,
    SUM(r.monto_devuelto)                                         AS monto_devuelto,
    ROUND(100 * SUM(r.monto_devuelto) / SUM(r.revenue_bruto), 2)  AS pct_devoluciones
FROM resumen_producto_diario r
JOIN dim_producto p ON p.codigo_producto = r.codigo_producto
GROUP BY p.categoria
HAVING SUM(r.revenue_bruto) > 0
ORDER BY revenue_bruto DESC;
