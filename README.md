# revenueForecast

Local document-ingestion pipeline. Drop PDFs or images into `data/inbox/`, get structured rows in SQLite, export to Excel, browse via Streamlit. All inference runs locally on Apple Silicon via `llama.cpp`.

## Stack

- **OCR**: GLM-OCR 0.9B (llama.cpp) — swap to PaddleOCR-VL 1.5 in `config.toml` when ready.
- **Structuring**: Qwen 3.5-4B VL (llama.cpp).
- **Storage**: SQLite.
- **Viz**: Streamlit + Plotly.
- **Export**: pandas + openpyxl.

## One-time setup

```bash
brew install llama.cpp
uv sync
```

## Run

```bash
# 1. Start both llama-servers (runs in background)
./scripts/start_models.sh

# 2. Drop files into data/inbox/ then:
uv run rf-ingest

# 3. Explore
uv run rf-dashboard           # http://localhost:8501
uv run rf-export              # writes data/export.xlsx

# Stop servers
./scripts/stop_models.sh
```

## Config

Edit `config.toml` to change model, ports, paths, timeouts.

## Layout

```
src/        pipeline modules
scripts/    llama-server launchers
data/       inbox / processed / failed / data.db
tests/      unit + integration
```
# locally
