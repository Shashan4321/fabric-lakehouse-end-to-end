# Fabric notebook: 01_bronze_ingest
# Attach to Lakehouse "lh_supplychain". Source files are uploaded to Files/landing/.
# Writes raw Delta tables bronze_* with ingestion metadata. No business logic here:
# bronze is the replayable copy of what the source systems sent.

# %% [parameters]
landing = "Files/landing"

# %%
from pyspark.sql import functions as F

csv_sources = {
    "bronze_items": "items.csv",
    "bronze_suppliers": "suppliers.csv",
    "bronze_warehouses": "warehouses.csv",
    "bronze_purchase_orders": "purchase_orders.csv",
    "bronze_stock_issues": "stock_issues.csv",
}

for table, file in csv_sources.items():
    df = (
        spark.read.option("header", True)          # all strings in bronze, typed in silver
        .csv(f"{landing}/{file}")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.lit(file))
    )
    df.write.mode("overwrite").format("delta").saveAsTable(table)
    print(table, df.count())

# %%
# Goods receipts arrive as monthly JSON arrays from the WMS, with a nested po_ref struct.
grn = (
    spark.read.option("multiLine", True)
    .json(f"{landing}/goods_receipts/*.json")
    .withColumn("_ingested_at", F.current_timestamp())
    .withColumn("_source_file", F.input_file_name())
)
grn.write.mode("overwrite").format("delta").saveAsTable("bronze_goods_receipts")
print("bronze_goods_receipts", grn.count())
