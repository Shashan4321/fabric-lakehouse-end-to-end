-- Flatten the nested po_ref struct, standardise codes, drop duplicate GRNs,
-- and keep only valid rows. Invalid rows go to silver_receipts_quarantine.
SELECT
    r.receipt_id,
    r.receipt_ts,
    r.receipt_date,
    r.warehouse_code,
    r.po_number,
    r.po_line,
    r.received_qty
FROM (
    SELECT
        TRIM(receipt_id) AS receipt_id,
        CAST(receipt_ts AS TIMESTAMP) AS receipt_ts,
        CAST(CAST(receipt_ts AS TIMESTAMP) AS DATE) AS receipt_date,
        UPPER(TRIM(warehouse)) AS warehouse_code,
        TRIM(po_ref.number) AS po_number,
        CAST(po_ref.line AS INT) AS po_line,
        CAST(qty AS INT) AS received_qty,
        ROW_NUMBER() OVER (PARTITION BY TRIM(receipt_id) ORDER BY _ingested_at) AS rn
    FROM bronze_goods_receipts
) AS r
INNER JOIN silver_purchase_orders AS p
    ON r.po_number = p.po_number AND r.po_line = p.po_line
WHERE r.rn = 1 AND r.received_qty > 0
