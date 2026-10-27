-- Pregunta 6: ¿Qué productos no tienen descripción consistente? ¿Cuántos códigos únicos existen?

-- 6a. Productos con más de una descripción original en las transacciones cargadas.
--     Se muestran también cuántas variantes quedan al normalizar a mayúsculas.
WITH lineas AS (
    SELECT codigo_producto, descripcion_original FROM fact_ventas
    UNION ALL
    SELECT codigo_producto, descripcion_original FROM fact_devoluciones
)
SELECT
    l.codigo_producto,
    p.nombre                                          AS nombre_canonico,
    COUNT(DISTINCT l.descripcion_original)            AS variantes_originales,
    COUNT(DISTINCT UPPER(l.descripcion_original))     AS variantes_en_mayusculas,
    STRING_AGG(DISTINCT l.descripcion_original, ' | ') AS descripciones
FROM lineas l
JOIN dim_producto p ON p.codigo_producto = l.codigo_producto
GROUP BY l.codigo_producto, p.nombre
HAVING COUNT(DISTINCT l.descripcion_original) > 1
ORDER BY variantes_originales DESC, l.codigo_producto;

-- 6b. Códigos únicos de producto: en el repositorio y en todas las transacciones recibidas
--     (incluye los códigos que solo aparecen en registros rechazados, como POST o DOT).
SELECT
    (SELECT COUNT(*) FROM dim_producto) AS codigos_en_repositorio,
    (SELECT COUNT(DISTINCT codigo_producto) FROM (
        SELECT codigo_producto FROM dim_producto
        UNION
        SELECT codigo_producto FROM log_rechazos
    ) todos)                            AS codigos_en_todas_las_fuentes;
