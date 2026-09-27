# Fabric notebook: 03_data_quality_gate
# Fails the pipeline run (raises) if any check returns failures > 0, so a bad load
# never reaches the Direct Lake semantic model.

# %% [parameters]
sql_root = "/lakehouse/default/Files/sql"

# %%
from pathlib import Path

checks = spark.sql(Path(f"{sql_root}/dq/checks.sql").read_text()).toPandas()
display(checks)
failed = checks[checks["failures"] > 0]
if len(failed):
    raise RuntimeError(f"Data-quality gate failed:\n{failed.to_string(index=False)}")
print("All data-quality checks passed")
