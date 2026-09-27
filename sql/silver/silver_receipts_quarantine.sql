-- Every bronze receipt that did not make it to silver, with the reason.
SELECT
    b.receipt_id,
    b.receipt_ts,
    b.po_ref.number AS po_number,
    b.qty,
    CASE
        WHEN b.rn > 1 THEN 'duplicate_receipt_id'
        WHEN b.qty <= 0 THEN 'non_positive_qty'
        WHEN p.po_number IS NULL THEN 'unknown_po_line'
        ELSE 'other'
    END AS reason
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY TRIM(receipt_id) ORDER BY _ingested_at) AS rn
    FROM bronze_goods_receipts
) AS b
LEFT JOIN silver_purchase_orders AS p
    ON TRIM(b.po_ref.number) = p.po_number AND CAST(b.po_ref.line AS INT) = p.po_line
WHERE b.rn > 1 OR b.qty <= 0 OR p.po_number IS NULL
