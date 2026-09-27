-- Monthly stock movements and closing balance per item and warehouse.
WITH moves AS (
    SELECT
        p.item_code,
        r.warehouse_code,
        YEAR(r.receipt_date) * 100 + MONTH(r.receipt_date) AS year_month,
        r.received_qty AS qty_in,
        0 AS qty_out
    FROM silver_goods_receipts AS r
    INNER JOIN silver_purchase_orders AS p
        ON r.po_number = p.po_number AND r.po_line = p.po_line
    UNION ALL
    SELECT
        item_code,
        warehouse_code,
        YEAR(issue_date) * 100 + MONTH(issue_date) AS year_month,
        0 AS qty_in,
        issued_qty AS qty_out
    FROM silver_stock_issues
),

monthly AS (
    SELECT
        item_code,
        warehouse_code,
        year_month,
        SUM(qty_in) AS qty_in,
        SUM(qty_out) AS qty_out
    FROM moves
    GROUP BY item_code, warehouse_code, year_month
)

SELECT
    i.item_key,
    w.warehouse_key,
    m.year_month,
    m.qty_in,
    m.qty_out,
    SUM(m.qty_in - m.qty_out) OVER (
        PARTITION BY m.item_code, m.warehouse_code ORDER BY m.year_month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS closing_qty,
    CAST(
        SUM(m.qty_in - m.qty_out) OVER (
            PARTITION BY m.item_code, m.warehouse_code ORDER BY m.year_month
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) * i.unit_cost AS DECIMAL(18, 2)
    ) AS closing_value
FROM monthly AS m
INNER JOIN dim_item AS i ON m.item_code = i.item_code
INNER JOIN dim_warehouse AS w ON m.warehouse_code = w.warehouse_code
