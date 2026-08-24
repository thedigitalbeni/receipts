"""
Receipts Backend — Vercel Serverless Entry Point

Vercel's Python runtime requires the ASGI app to be exposed via a module-level
`app` variable in a file located under an `api/` directory.

This file simply imports and re-exports the FastAPI app from the main module.
All routes, middleware, and configuration are unchanged — this is a thin adapter.
"""

import sys
import os

# Add the backend root to sys.path so `from app.xxx import ...` works.
# Vercel runs this file from the `backend/` root (the project root set in
# Vercel's dashboard), so `app/` is already a sibling.  The sys.path insert
# is a safety net for local `vercel dev` testing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: F401 — Vercel discovers the `app` symbol

# Expose the ASGI app at module level so Vercel's Python runtime can mount it.
__all__ = ["app"]
