"""Bronze -> Silver -> Gold, run locally on DuckDB with the *same* SQL the Fabric notebooks run.

The SQL in ``sql/`` is a portable subset of Spark SQL and DuckDB. The only dialect
difference (date arithmetic) is a ``{{ days_between(a, b) }}`` placeholder rendered by
:func:`render`. In Fabric, ``fabric/notebooks/*.py`` render the same files for Spark and
write Delta tables to the Lakehouse; here they become DuckDB tables so CI can test them.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql"

SILVER = [
    "silver_items",
    "silver_suppliers",
    "silver_warehouses",
    "silver_purchase_orders",
    "silver_goods_receipts",
    "silver_receipts_quarantine",
    "silver_stock_issues",
]
GOLD = ["dim_item", "dim_supplier", "dim_warehouse", "fact_po_line", "fact_inventory_monthly"]

_DAYS = re.compile(r"\{\{\s*days_between\('([^']+)',\s*'([^']+)'\)\s*\}\}")


def render(sql: str, dialect: str) -> str:
    """Render dialect placeholders. ``days_between(a, b)`` = whole days from a to b."""
    if dialect == "spark":
        return _DAYS.sub(r"DATEDIFF(\2, \1)", sql)
    if dialect == "duckdb":
        return _DAYS.sub(r"DATE_DIFF('day', \1, \2)", sql)
    raise ValueError(dialect)


def dim_date(start: str = "2024-01-01", end: str = "2026-03-31") -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    d["date_key"] = d["date"].dt.strftime("%Y%m%d").astype(int)
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    d["month_name"] = d["date"].dt.strftime("%b")
    d["year_month"] = d["year"] * 100 + d["month"]
    d["quarter"] = d["date"].dt.quarter
    d["fiscal_year"] = d["year"].where(d["month"] < 4, d["year"] + 1)  # Indian FY
    return d


def load_bronze(con: duckdb.DuckDBPyConnection, landing: Path) -> dict[str, int]:
    """Landing files -> bronze tables, adding ingestion metadata (as the Fabric notebook does)."""
    csvs = {
        "bronze_items": "items.csv",
        "bronze_suppliers": "suppliers.csv",
        "bronze_warehouses": "warehouses.csv",
        "bronze_purchase_orders": "purchase_orders.csv",
        "bronze_stock_issues": "stock_issues.csv",
    }
    for table, f in csvs.items():
        con.execute(f"""CREATE OR REPLACE TABLE {table} AS
            SELECT *, current_timestamp AS _ingested_at, '{f}' AS _source_file
            FROM read_csv_auto('{landing / f}', header = true, all_varchar = true)""")
    con.execute(f"""CREATE OR REPLACE TABLE bronze_goods_receipts AS
        SELECT *, current_timestamp AS _ingested_at, filename AS _source_file
        FROM read_json_auto('{landing / "goods_receipts" / "*.json"}', filename = true)""")
    return {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in [*csvs, "bronze_goods_receipts"]
    }


def build(con: duckdb.DuckDBPyConnection) -> None:
    for name in SILVER:
        sql = render((SQL / "silver" / f"{name}.sql").read_text(), "duckdb")
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")
    con.register("dim_date_df", dim_date())
    con.execute("CREATE OR REPLACE TABLE dim_date AS SELECT * FROM dim_date_df")
    for name in GOLD:
        sql = render((SQL / "gold" / f"{name}.sql").read_text(), "duckdb")
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")


def quality_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute((SQL / "dq" / "checks.sql").read_text()).df()


def run(
    landing: Path = ROOT / "data" / "landing",
    db: str = ":memory:",
    export: Path | None = ROOT / "data" / "gold",
) -> tuple[duckdb.DuckDBPyConnection, pd.DataFrame]:
    con = duckdb.connect(db)
    load_bronze(con, landing)
    build(con)
    checks = quality_checks(con)
    if (checks["failures"] > 0).any():
        raise RuntimeError("Data-quality gate failed:\n" + checks.to_string(index=False))
    if export:
        export.mkdir(parents=True, exist_ok=True)
        for t in ["dim_date", *GOLD]:
            con.execute(f"COPY {t} TO '{export / (t + '.parquet')}' (FORMAT parquet)")
    return con, checks


def kpis(con: duckdb.DuckDBPyConnection) -> dict:
    q = lambda s: con.execute(s).fetchone()  # noqa: E731
    otif, ontime, infull, lead = q("""SELECT AVG(is_otif) * 100, AVG(is_on_time) * 100,
        AVG(is_in_full) * 100, MEDIAN(lead_time_days) FROM fact_po_line
        WHERE first_receipt_date IS NOT NULL""")
    worst = con.execute("""SELECT s.supplier_code, ROUND(AVG(f.is_otif) * 100, 1) AS otif
        FROM fact_po_line f JOIN dim_supplier s USING (supplier_key)
        WHERE f.first_receipt_date IS NOT NULL GROUP BY 1 ORDER BY 2 LIMIT 3""").fetchall()
    stock = q("""SELECT SUM(closing_value) FROM (
        SELECT closing_value, ROW_NUMBER() OVER (PARTITION BY item_key, warehouse_key
               ORDER BY year_month DESC) AS rn FROM fact_inventory_monthly) WHERE rn = 1""")[0]
    quarantine = dict(
        con.execute(
            "SELECT reason, COUNT(*) FROM silver_receipts_quarantine GROUP BY 1 ORDER BY 1"
        ).fetchall()
    )
    return {
        "otif_pct": round(otif, 1),
        "on_time_pct": round(ontime, 1),
        "in_full_pct": round(infull, 1),
        "median_lead_time_days": float(lead),
        "worst_suppliers_otif": worst,
        "closing_stock_value": float(stock),
        "quarantined_receipts": quarantine,
        "rows": {
            t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in [
                "bronze_goods_receipts",
                "silver_goods_receipts",
                "fact_po_line",
                "fact_inventory_monthly",
            ]
        },
    }


if __name__ == "__main__":
    import json

    c, chk = run()
    print(chk.to_string(index=False))
    print(json.dumps(kpis(c), indent=2, default=str))
