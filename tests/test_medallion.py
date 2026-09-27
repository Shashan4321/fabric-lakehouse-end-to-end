"""Tests for the medallion SQL (the same files the Fabric notebooks run)."""

import re
from pathlib import Path

import pytest

from fabriclh import landing, medallion

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    land = tmp_path_factory.mktemp("landing")
    landing.generate(land)
    con, checks = medallion.run(land, export=None)
    return con, checks


def test_quality_gate_passes(built):
    _, checks = built
    assert (checks["failures"] == 0).all(), checks


def test_every_bronze_receipt_is_accounted_for(built):
    con, _ = built
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    reasons = dict(
        con.execute("SELECT reason, COUNT(*) FROM silver_receipts_quarantine GROUP BY 1").fetchall()
    )
    assert reasons == {"duplicate_receipt_id": 40, "non_positive_qty": 8, "unknown_po_line": 15}
    assert q("SELECT COUNT(*) FROM bronze_goods_receipts") == (
        q("SELECT COUNT(*) FROM silver_goods_receipts") + sum(reasons.values())
    )


def test_codes_are_conformed(built):
    con, _ = built
    bad = con.execute("""SELECT COUNT(*) FROM silver_goods_receipts
        WHERE warehouse_code <> UPPER(TRIM(warehouse_code))""").fetchone()[0]
    assert bad == 0


def test_otif_is_consistent(built):
    con, _ = built
    # OTIF implies both on-time... in full by the promise date implies in full overall
    n = con.execute("SELECT COUNT(*) FROM fact_po_line WHERE is_otif = 1 AND is_in_full = 0").fetchone()[0]
    assert n == 0
    k = medallion.kpis(con)
    assert 0 < k["otif_pct"] <= k["in_full_pct"]


def test_inventory_balance_equals_net_movements(built):
    con, _ = built
    closing = con.execute("""SELECT SUM(closing_qty) FROM (SELECT closing_qty, ROW_NUMBER() OVER
        (PARTITION BY item_key, warehouse_key ORDER BY year_month DESC) rn
        FROM fact_inventory_monthly) WHERE rn = 1""").fetchone()[0]
    net = con.execute("SELECT SUM(qty_in) - SUM(qty_out) FROM fact_inventory_monthly").fetchone()[0]
    assert closing == net


def test_spark_and_duckdb_rendering():
    sql = "SELECT {{ days_between('a.d1', 'b.d2') }} AS x"
    assert medallion.render(sql, "spark") == "SELECT DATEDIFF(b.d2, a.d1) AS x"
    assert medallion.render(sql, "duckdb") == "SELECT DATE_DIFF('day', a.d1, b.d2) AS x"


def test_no_duckdb_only_syntax_in_shared_sql():
    """The SQL must also run on Fabric Spark: no QUALIFY, no ::casts, no DuckDB-only functions."""
    for f in (ROOT / "sql").rglob("*.sql"):
        text = f.read_text().upper()
        for bad in ["QUALIFY", "::", "DATE_DIFF(", "STRFTIME(", "GENERATE_SERIES", "MEDIAN("]:
            assert bad not in text, f"{f.name} uses {bad}"


def test_semantic_model_matches_gold_columns(built):
    con, _ = built
    tdir = ROOT / "fabric" / "SupplyChain.SemanticModel" / "definition" / "tables"
    for tmdl in tdir.glob("*.tmdl"):
        text = tmdl.read_text(encoding="utf-8")
        table = re.search(r"^table (\S+)", text, re.M).group(1)
        cols = set(re.findall(r"^\tcolumn (\S+)", text, re.M))
        actual = {
            r[0]
            for r in con.execute(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
            ).fetchall()
        }
        assert cols == actual, table
