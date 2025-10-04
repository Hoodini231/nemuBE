# NemuBE FastAPI

A minimal FastAPI app with a router for items.

Quick start

1. Create and activate a virtual environment (macOS / zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/items to see the items, and http://127.0.0.1:8000/docs for the interactive docs.
