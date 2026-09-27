SELECT
    TRIM(po_number) AS po_number,
    CAST(po_line AS INT) AS po_line,
    UPPER(TRIM(supplier_code)) AS supplier_code,
    UPPER(TRIM(item_code)) AS item_code,
    UPPER(TRIM(warehouse_code)) AS warehouse_code,
    CAST(order_date AS DATE) AS order_date,
    CAST(promised_date AS DATE) AS promised_date,
    CAST(ordered_qty AS INT) AS ordered_qty,
    CAST(unit_price AS DECIMAL(12, 2)) AS unit_price
FROM bronze_purchase_orders
