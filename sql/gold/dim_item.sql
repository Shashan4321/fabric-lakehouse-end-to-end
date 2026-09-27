SELECT
    ROW_NUMBER() OVER (ORDER BY item_code) AS item_key,
    item_code,
    item_name,
    category,
    uom,
    unit_cost
FROM silver_items
