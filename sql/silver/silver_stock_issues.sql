SELECT
    CAST(issue_date AS DATE) AS issue_date,
    UPPER(TRIM(item_code)) AS item_code,
    UPPER(TRIM(warehouse_code)) AS warehouse_code,
    CAST(issued_qty AS INT) AS issued_qty
FROM bronze_stock_issues
WHERE CAST(issued_qty AS INT) > 0
