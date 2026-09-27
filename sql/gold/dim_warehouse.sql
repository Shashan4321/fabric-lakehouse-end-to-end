SELECT
    ROW_NUMBER() OVER (ORDER BY warehouse_code) AS warehouse_key,
    warehouse_code,
    warehouse_name,
    region
FROM silver_warehouses
