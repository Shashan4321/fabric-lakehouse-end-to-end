-- Fabric Warehouse (T-SQL). Cross-database queries read the Lakehouse gold tables
-- through its SQL analytics endpoint, with no data copy.
CREATE SCHEMA rpt;
GO

CREATE VIEW rpt.supplier_scorecard AS
SELECT
    s.supplier_code,
    s.supplier_name,
    s.country,
    COUNT(*) AS po_lines,
    CAST(AVG(CAST(f.is_otif AS FLOAT)) * 100 AS DECIMAL(5, 1)) AS otif_pct,
    CAST(AVG(CAST(f.is_on_time AS FLOAT)) * 100 AS DECIMAL(5, 1)) AS on_time_pct,
    CAST(AVG(CAST(f.is_in_full AS FLOAT)) * 100 AS DECIMAL(5, 1)) AS in_full_pct,
    AVG(f.lead_time_days) AS avg_lead_time_days,
    SUM(f.order_value) AS order_value
FROM lh_supplychain.dbo.fact_po_line AS f
INNER JOIN lh_supplychain.dbo.dim_supplier AS s ON f.supplier_key = s.supplier_key
WHERE f.first_receipt_date IS NOT NULL
GROUP BY s.supplier_code, s.supplier_name, s.country;
GO

CREATE VIEW rpt.stock_position AS
SELECT
    w.warehouse_name,
    i.category,
    SUM(x.closing_qty) AS closing_qty,
    SUM(x.closing_value) AS closing_value
FROM (
    SELECT
        item_key, warehouse_key, closing_qty, closing_value,
        ROW_NUMBER() OVER (PARTITION BY item_key, warehouse_key ORDER BY year_month DESC) AS rn
    FROM lh_supplychain.dbo.fact_inventory_monthly
) AS x
INNER JOIN lh_supplychain.dbo.dim_item AS i ON x.item_key = i.item_key
INNER JOIN lh_supplychain.dbo.dim_warehouse AS w ON x.warehouse_key = w.warehouse_key
WHERE x.rn = 1
GROUP BY w.warehouse_name, i.category;
GO
