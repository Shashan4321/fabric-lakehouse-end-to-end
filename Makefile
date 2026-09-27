.PHONY: landing run test lint
landing:   ## synthetic source files -> data/landing (what you upload to OneLake Files/landing)
	PYTHONPATH=src python -m fabriclh.landing
run:       ## bronze -> silver -> gold -> DQ gate on DuckDB, gold exported as Parquet
	PYTHONPATH=src python -m fabriclh.medallion
test:
	pytest -q
lint:
	ruff check . && ruff format --check . && sqlfluff lint sql/
