# Demo observations

This small fixture is derived from the same observation-oriented schema as the
provided dataset. It exists to make local and hosted demonstrations reproducible
without downloading the full source object.

Build the analytical artifact with:

```bash
python3 -m sales_intelligence etl \
  data/demo/observations.jsonl \
  --output data/processed/demo-companies.parquet \
  --dataset-version demo-v1
```

The production ETL path still accepts the provided Backblaze URL through
`RAW_DATASET_URL`. The demo fixture must not be presented as a full-dataset
result.
