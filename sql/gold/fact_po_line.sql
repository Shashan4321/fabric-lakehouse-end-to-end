-- One row per PO line with delivery performance.
-- OTIF = the full ordered quantity was received on or before the promised date.
WITH rec AS (
    SELECT
        r.po_number,
        r.po_line,
        SUM(r.received_qty) AS received_qty,
        SUM(CASE WHEN r.receipt_date <= p.promised_date THEN r.received_qty ELSE 0 END)
            AS received_by_promise_qty,
        MIN(r.receipt_date) AS first_receipt_date,
        MAX(r.receipt_date) AS last_receipt_date
    FROM silver_goods_receipts AS r
    INNER JOIN silver_purchase_orders AS p
        ON r.po_number = p.po_number AND r.po_line = p.po_line
    GROUP BY r.po_number, r.po_line
)

SELECT
    p.po_number,
    p.po_line,
    s.supplier_key,
    i.item_key,
    w.warehouse_key,
    p.order_date,
    p.promised_date,
    p.ordered_qty,
    p.unit_price,
    rec.first_receipt_date,
    rec.last_receipt_date,
    CAST(p.ordered_qty * p.unit_price AS DECIMAL(18, 2)) AS order_value,
    COALESCE(rec.received_qty, 0) AS received_qty,
    CAST(COALESCE(rec.received_qty, 0) * p.unit_price AS DECIMAL(18, 2)) AS received_value,
    {{ days_between('p.order_date', 'rec.first_receipt_date') }} AS lead_time_days,
    CASE WHEN rec.first_receipt_date <= p.promised_date THEN 1 ELSE 0 END AS is_on_time,
    CASE WHEN COALESCE(rec.received_qty, 0) >= p.ordered_qty THEN 1 ELSE 0 END AS is_in_full,
    CASE
        WHEN COALESCE(rec.received_by_promise_qty, 0) >= p.ordered_qty THEN 1 ELSE 0
    END AS is_otif,
    CAST(YEAR(p.order_date) * 10000 + MONTH(p.order_date) * 100 + DAY(p.order_date) AS INT)
        AS order_date_key
FROM silver_purchase_orders AS p
LEFT JOIN rec ON p.po_number = rec.po_number AND p.po_line = rec.po_line
INNER JOIN dim_supplier AS s ON p.supplier_code = s.supplier_code
INNER JOIN dim_item AS i ON p.item_code = i.item_code
INNER JOIN dim_warehouse AS w ON p.warehouse_code = w.warehouse_code
