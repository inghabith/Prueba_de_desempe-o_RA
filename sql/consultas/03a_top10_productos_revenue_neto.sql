-- Pregunta 3a: ¿Cuáles son los 10 productos con mayor revenue neto?
SELECT
    p.codigo_producto,
    p.nombre,
    p.categoria,
    SUM(r.revenue_neto) AS revenue_neto
FROM resumen_producto_diario r
JOIN dim_producto p ON p.codigo_producto = r.codigo_producto
GROUP BY p.codigo_producto, p.nombre, p.categoria
ORDER BY revenue_neto DESC
LIMIT 10;
