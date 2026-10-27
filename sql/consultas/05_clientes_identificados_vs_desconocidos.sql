-- Pregunta 5: ¿Hay diferencia en el comportamiento de compra entre clientes identificados
-- y transacciones sin customer ID? (Aplica porque decidimos incluirlas como 'DESCONOCIDO').
SELECT
    CASE WHEN cliente_id = 'DESCONOCIDO' THEN 'Sin customer ID' ELSE 'Identificado' END AS tipo_cliente,
    COUNT(DISTINCT factura)                                  AS transacciones,
    SUM(revenue_bruto)                                       AS revenue_bruto,
    ROUND(SUM(revenue_bruto) / COUNT(DISTINCT factura), 2)  AS ticket_promedio,
    ROUND(COUNT(*)::NUMERIC / COUNT(DISTINCT factura), 1)   AS lineas_por_factura,
    ROUND(AVG(cantidad), 1)                                  AS unidades_por_linea,
    ROUND(AVG(precio_unitario), 2)                           AS precio_unitario_promedio
FROM fact_ventas
GROUP BY 1
ORDER BY 1;
