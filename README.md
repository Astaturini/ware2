# Warehouse Simulator

Warehouse simulation and decision-support application for testing warehouse layouts,
AMR policies, demand profiles, cost KPIs, and operational robustness.

The project is packaged for local or private Docker deployment. The live simulation
and decision-job manager keep state in the application process, so the container
intentionally runs one Gunicorn worker.

## Requirements

- Python 3.13 recommended
- Docker, if using the container workflow

## Local setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in a browser.

## Test and verify

```bash
python -m compileall -q app.py analysis decision experiment simulation tests
python -m pytest -q
python -m pip check
```

## Docker

Build and run the production container with a persistent data directory:

```bash
docker build -t warehouse-sim .
mkdir -p .docker-data
docker run --rm --name warehouse-sim \
  -p 8000:8000 \
  -v "$PWD/.docker-data:/app/data" \
  warehouse-sim
```

Open `http://127.0.0.1:8000`. The health endpoint is
`http://127.0.0.1:8000/healthz`.

Generated runs and decision artifacts belong in the mounted `data` directory and
should not be committed to GitHub. Keep only deliberately selected sample data in
the repository.

This deployment profile is intended for local or trusted private networks. Before
exposing it to the public internet, add authentication, authorization, rate
limiting, request limits, and a managed job queue. Do not run multiple Gunicorn
workers until application state and decision jobs are externalized.

## Project documentation

The detailed API and storage contract is in [docs/API_SURFACE.md](docs/API_SURFACE.md).
