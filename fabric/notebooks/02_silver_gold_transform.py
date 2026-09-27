# Fabric notebook: 02_silver_gold_transform
# Runs the SAME SQL files that CI tests on DuckDB (upload the repo's sql/ folder to
# Files/sql/). Silver = cleaned & conformed; Gold = star schema for Direct Lake.

# %% [parameters]
sql_root = "/lakehouse/default/Files/sql"

# %%
import re
from pathlib import Path

import pandas as pd

SILVER = ["silver_items", "silver_suppliers", "silver_warehouses", "silver_purchase_orders",
          "silver_goods_receipts", "silver_receipts_quarantine", "silver_stock_issues"]
GOLD = ["dim_item", "dim_supplier", "dim_warehouse", "fact_po_line", "fact_inventory_monthly"]
_DAYS = re.compile(r"\{\{\s*days_between\('([^']+)',\s*'([^']+)'\)\s*\}\}")


def render_spark(sql: str) -> str:
    return _DAYS.sub(r"DATEDIFF(\2, \1)", sql)


def build(layer: str, name: str) -> None:
    sql = render_spark(Path(f"{sql_root}/{layer}/{name}.sql").read_text())
    spark.sql(f"CREATE OR REPLACE TABLE {name} USING DELTA AS {sql}")
    print(layer, name, spark.table(name).count())


# %%
for t in SILVER:
    build("silver", t)

# %%
# Date dimension (Indian FY April-March)
d = pd.DataFrame({"date": pd.date_range("2024-01-01", "2026-03-31", freq="D")})
d["date_key"] = d["date"].dt.strftime("%Y%m%d").astype(int)
d["year"], d["month"], d["quarter"] = d["date"].dt.year, d["date"].dt.month, d["date"].dt.quarter
d["month_name"] = d["date"].dt.strftime("%b")
d["year_month"] = d["year"] * 100 + d["month"]
d["fiscal_year"] = d["year"].where(d["month"] < 4, d["year"] + 1)
spark.createDataFrame(d).write.mode("overwrite").format("delta").saveAsTable("dim_date")

for t in GOLD:
    build("gold", t)

# %%
# V-Order + optimize for Direct Lake read performance
for t in ["dim_date", *GOLD]:
    spark.sql(f"OPTIMIZE {t} VORDER")
