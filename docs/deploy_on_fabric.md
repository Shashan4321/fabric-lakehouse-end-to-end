# Deploy on Microsoft Fabric (free trial)

1. **Workspace.** Start a Fabric trial and create a workspace, e.g. `ws-supplychain-demo`.
2. **Lakehouse.** Create Lakehouse `lh_supplychain`.
3. **Landing files.** Run `make landing` locally and upload `data/landing/*` to `Files/landing/` (keep the `goods_receipts/` sub-folder). Upload the repo's `sql/` folder to `Files/sql/`.
4. **Notebooks.** Import `fabric/notebooks/01_bronze_ingest.py`, `02_silver_gold_transform.py`, `03_data_quality_gate.py` (Workspace → Import → Notebook) and attach each to `lh_supplychain` as the default lakehouse.
5. **Pipeline.** Create Data pipeline `pl_supplychain_medallion` with the four activities in [`fabric/pipeline/pl_supplychain_medallion.json`](../fabric/pipeline/pl_supplychain_medallion.json): Bronze → Silver & Gold → DQ gate → semantic model refresh. Replace the `<... id>` placeholders by selecting the items in the activity settings. Schedule it daily.
6. **Warehouse.** Create Warehouse `wh_reporting` and run [`fabric/warehouse/01_views.sql`](../fabric/warehouse/01_views.sql). The views read the Lakehouse gold tables through cross-database queries, with no copy.
7. **Direct Lake semantic model.** Use Git integration (Workspace settings → Git) or Tabular Editor to deploy `fabric/SupplyChain.SemanticModel`. Set the `DatabaseQuery` expression to your Lakehouse SQL analytics endpoint.
8. **Report.** Build pages for Supplier scorecard (OTIF, on-time, in-full, lead time, rank), Stock position (closing value by warehouse and category) and Trend. Screenshot them into `docs/img/` and link them from the README.

## Evidence checklist (add to README when done)

- [ ] Screenshot: Lakehouse explorer showing bronze / silver / gold tables
- [ ] Screenshot: pipeline run history (all green)
- [ ] Screenshot: DQ gate output
- [ ] Screenshot: Direct Lake model diagram + report pages
- [ ] Capacity Metrics: CU used by the daily run
