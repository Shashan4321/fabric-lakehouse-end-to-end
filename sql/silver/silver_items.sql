-- Conformed item master: trimmed, upper-cased codes, one row per item.
SELECT
    UPPER(TRIM(item_code)) AS item_code,
    TRIM(item_name) AS item_name,
    TRIM(category) AS category,
    UPPER(TRIM(uom)) AS uom,
    CAST(unit_cost AS DECIMAL(12, 2)) AS unit_cost
FROM bronze_items
