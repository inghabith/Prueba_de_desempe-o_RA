-- Pregunta 4: ¿Qué países concentran la mayor parte de las transacciones y cómo varía el ticket promedio?
-- Una transacción es una factura. Ticket promedio = revenue bruto / número de facturas.
SELECT
    pais,
    COUNT(DISTINCT factura)                                                     AS transacciones,
    ROUND(100.0 * COUNT(DISTINCT factura) / SUM(COUNT(DISTINCT factura)) OVER (), 2) AS pct_transacciones,
    SUM(revenue_bruto)                                                          AS revenue_bruto,
    ROUND(SUM(revenue_bruto) / COUNT(DISTINCT factura), 2)                     AS ticket_promedio
FROM fact_ventas
GROUP BY pais
ORDER BY transacciones DESC;
