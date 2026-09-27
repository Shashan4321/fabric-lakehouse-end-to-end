SELECT
    ROW_NUMBER() OVER (ORDER BY supplier_code) AS supplier_key,
    supplier_code,
    supplier_name,
    country
FROM silver_suppliers
