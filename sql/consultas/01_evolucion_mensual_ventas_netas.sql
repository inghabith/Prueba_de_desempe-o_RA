-- Pregunta 1: ¿Cuál fue la evolución mensual de las ventas netas (descontando devoluciones)?
-- Usa el resumen diario, donde revenue_neto = revenue_bruto - monto_devuelto.
SELECT
    TO_CHAR(DATE_TRUNC('month', fecha), 'YYYY-MM') AS mes,
    SUM(revenue_bruto)                           AS revenue_bruto,
    SUM(monto_devuelto)                          AS devoluciones,
    SUM(revenue_neto)                            AS revenue_neto
FROM resumen_producto_diario
GROUP BY 1
ORDER BY 1;
