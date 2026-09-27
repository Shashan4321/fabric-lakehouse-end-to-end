"""Generate synthetic supply-chain source files, as they would land in OneLake ``Files/landing``.

Sources (deliberately messy, like real ERP/WMS exports):
* ``items.csv``, ``suppliers.csv``, ``warehouses.csv``   master data
* ``purchase_orders.csv``                                PO lines with promised dates
* ``goods_receipts/*.json``                              one JSON file per month from the WMS
* ``stock_issues.csv``                                   daily issues (sales / consumption)

Injected problems: duplicate receipt records, lower-case / padded codes, a few receipts
for unknown PO lines, negative quantities, late and partial deliveries.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 5
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
WAREHOUSES = [
    ("WH-GGN", "Gurugram DC", "North"),
    ("WH-BLR", "Bengaluru DC", "South"),
    ("WH-BOM", "Mumbai DC", "West"),
    ("WH-MAA", "Chennai DC", "South"),
    ("WH-CCU", "Kolkata DC", "East"),
]
CATEGORIES = {
    "Raw Material": (20, 400),
    "Packaging": (5, 60),
    "Spares": (150, 5000),
    "Finished Goods": (300, 9000),
}


def generate(out: str | Path = "data/landing") -> dict[str, int]:
    rng = np.random.default_rng(SEED)
    out = Path(out)
    (out / "goods_receipts").mkdir(parents=True, exist_ok=True)

    wh = pd.DataFrame(WAREHOUSES, columns=["warehouse_code", "warehouse_name", "region"])
    cats = list(CATEGORIES)
    items = pd.DataFrame(
        {"item_code": [f"ITM-{i:04d}" for i in range(1, 201)], "category": rng.choice(cats, 200)}
    )
    items["item_name"] = items["category"].str.split().str[0] + " item " + items["item_code"].str[-4:]
    items["unit_cost"] = [round(float(rng.uniform(*CATEGORIES[c])), 2) for c in items["category"]]
    items["uom"] = np.where(items["category"] == "Raw Material", "KG", "EA")

    sup = pd.DataFrame(
        {
            "supplier_code": [f"SUP-{i:03d}" for i in range(1, 26)],
            "supplier_name": [f"Supplier {chr(64 + i)} Pvt Ltd" for i in range(1, 26)],
            "country": rng.choice(["India", "India", "India", "China", "Germany"], 25),
        }
    )
    # each supplier has a reliability profile (drives OTIF)
    reliability = dict(zip(sup["supplier_code"], rng.beta(8, 2, 25), strict=True))
    lead = dict(zip(sup["supplier_code"], rng.integers(5, 35, 25), strict=True))

    n_po = 6000
    po_dates = START + pd.to_timedelta(rng.integers(0, (END - START).days - 60, n_po), unit="D")
    po = pd.DataFrame(
        {
            "po_number": [f"PO-{i // 3 + 1:06d}" for i in range(n_po)],
            "po_line": [i % 3 + 1 for i in range(n_po)],
            "supplier_code": rng.choice(sup["supplier_code"], n_po),
            "item_code": rng.choice(items["item_code"], n_po),
            "warehouse_code": rng.choice(wh["warehouse_code"], n_po),
            "order_date": po_dates.date,
            "ordered_qty": rng.integers(10, 500, n_po),
        }
    )
    po["promised_date"] = [
        (pd.Timestamp(d) + pd.Timedelta(days=int(lead[s]))).date()
        for d, s in zip(po["order_date"], po["supplier_code"], strict=True)
    ]
    po = po.merge(items[["item_code", "unit_cost"]], on="item_code")
    po["unit_price"] = (po["unit_cost"] * rng.uniform(0.95, 1.1, len(po))).round(2)
    po = po.drop(columns="unit_cost")

    receipts = []
    for r in po.itertuples():
        rel = reliability[r.supplier_code]
        delay = 0 if rng.random() < rel else int(rng.integers(1, 20))
        qty_share = 1.0 if rng.random() < rel else float(rng.uniform(0.5, 0.95))
        first_qty = int(round(r.ordered_qty * qty_share))
        rdate = pd.Timestamp(r.promised_date) + pd.Timedelta(days=delay - int(rng.integers(0, 3)))
        receipts.append((r.po_number, r.po_line, rdate, first_qty, r.warehouse_code))
        if first_qty < r.ordered_qty and rng.random() < 0.6:  # balance arrives later
            receipts.append(
                (
                    r.po_number,
                    r.po_line,
                    rdate + pd.Timedelta(days=int(rng.integers(5, 25))),
                    r.ordered_qty - first_qty,
                    r.warehouse_code,
                )
            )
    rc = pd.DataFrame(
        receipts, columns=["po_number", "po_line", "receipt_ts", "received_qty", "warehouse_code"]
    )
    rc = rc[rc["receipt_ts"] <= END].reset_index(drop=True)
    rc["receipt_id"] = [f"GRN-{i:07d}" for i in range(1, len(rc) + 1)]
    # --- inject issues ---
    dup = rc.sample(40, random_state=SEED)
    rc = pd.concat([rc, dup], ignore_index=True)  # duplicate GRNs
    bad = rc.sample(15, random_state=SEED + 1).index
    rc.loc[bad, "po_number"] = "PO-999999"  # unknown PO
    neg = rc.sample(8, random_state=SEED + 2).index
    rc.loc[neg, "received_qty"] = -rc.loc[neg, "received_qty"]  # negative qty
    low = rc.sample(60, random_state=SEED + 3).index
    rc.loc[low, "warehouse_code"] = rc.loc[low, "warehouse_code"].str.lower() + " "

    rc["month"] = rc["receipt_ts"].dt.strftime("%Y-%m")
    n_files = 0
    for m, g in rc.groupby("month"):
        recs = [
            {
                "receipt_id": x.receipt_id,
                "receipt_ts": x.receipt_ts.isoformat(),
                "warehouse": x.warehouse_code,
                "po_ref": {"number": x.po_number, "line": int(x.po_line)},
                "qty": int(x.received_qty),
            }
            for x in g.itertuples()
        ]
        (out / "goods_receipts" / f"grn_{m}.json").write_text(json.dumps(recs))
        n_files += 1

    # daily stock issues: ~70% of received quantity is consumed over time
    iss = rc[rc["received_qty"] > 0].merge(
        po[["po_number", "po_line", "item_code"]], on=["po_number", "po_line"]
    )
    iss = iss.assign(
        issue_date=(iss["receipt_ts"] + pd.to_timedelta(rng.integers(1, 90, len(iss)), unit="D")).dt.date,
        issued_qty=(iss["received_qty"] * rng.uniform(0.4, 1.0, len(iss))).round().astype(int),
        warehouse_code=iss["warehouse_code"].str.strip().str.upper(),
    )
    iss = iss[pd.to_datetime(iss["issue_date"]) <= END][
        ["issue_date", "item_code", "warehouse_code", "issued_qty"]
    ]

    items.to_csv(out / "items.csv", index=False)
    sup.to_csv(out / "suppliers.csv", index=False)
    wh.to_csv(out / "warehouses.csv", index=False)
    po.to_csv(out / "purchase_orders.csv", index=False)
    iss.to_csv(out / "stock_issues.csv", index=False)
    return {
        "items": len(items),
        "suppliers": len(sup),
        "po_lines": len(po),
        "receipt_records": len(rc),
        "receipt_files": n_files,
        "issues": len(iss),
    }


if __name__ == "__main__":
    print(generate())
