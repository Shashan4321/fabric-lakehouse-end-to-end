-- Data-quality gate between layers. Each row: check name, failing rows. 0 = pass.
SELECT
    'bronze receipts = silver + quarantine' AS check_name,
    ABS(
        (SELECT COUNT(*) FROM bronze_goods_receipts)
        - (SELECT COUNT(*) FROM silver_goods_receipts)
        - (SELECT COUNT(*) FROM silver_receipts_quarantine)
    ) AS failures
UNION ALL
SELECT
    'duplicate receipt ids in silver' AS check_name,
    COUNT(*) - COUNT(DISTINCT receipt_id) AS failures
FROM silver_goods_receipts
UNION ALL
SELECT
    'PO lines lost between silver and gold' AS check_name,
    ABS((SELECT COUNT(*) FROM silver_purchase_orders) - (SELECT COUNT(*) FROM fact_po_line))
        AS failures
UNION ALL
SELECT
    'received value reconciles (paise)' AS check_name,
    CAST(ABS(
        (SELECT SUM(received_value) FROM fact_po_line)
        - (
            SELECT SUM(CAST(r.received_qty * p.unit_price AS DECIMAL(18, 2)))
            FROM silver_goods_receipts AS r
            INNER JOIN silver_purchase_orders AS p
                ON r.po_number = p.po_number AND r.po_line = p.po_line
        )
    ) * 100 AS BIGINT) AS failures
UNION ALL
SELECT
    'unknown warehouse codes in silver receipts' AS check_name,
    COUNT(*) AS failures
FROM silver_goods_receipts
WHERE warehouse_code NOT IN (SELECT warehouse_code FROM silver_warehouses)
