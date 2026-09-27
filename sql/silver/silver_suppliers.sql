SELECT
    UPPER(TRIM(supplier_code)) AS supplier_code,
    TRIM(supplier_name) AS supplier_name,
    TRIM(country) AS country
FROM bronze_suppliers
