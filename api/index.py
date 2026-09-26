"""
AETHERIS AI — Vercel serverless entrypoint.

Vercel's Python runtime auto-detects an exported ASGI `app` in files under
/api. This file does not duplicate any application logic — it only imports
the existing FastAPI app from backend/app/main.py so the exact same code
that runs locally also runs on Vercel.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.main import app  # noqa: E402,F401