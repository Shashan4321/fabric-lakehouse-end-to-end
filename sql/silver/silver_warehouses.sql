SELECT
    UPPER(TRIM(warehouse_code)) AS warehouse_code,
    TRIM(warehouse_name) AS warehouse_name,
    TRIM(region) AS region
FROM bronze_warehouses
