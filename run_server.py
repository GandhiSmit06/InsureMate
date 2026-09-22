"""Convenience runner script for InsureMate Phase 3 server."""

import sys
from pathlib import Path

# Add current directory and InsureMate to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import uvicorn
from phase3.main import app
from phase3.config import config

if __name__ == "__main__":
    print(f"Starting InsureMate Phase 3 on http://127.0.0.1:{config.PORT}")
    print(f"Swagger API Docs: http://localhost:{config.PORT}/docs (or http://127.0.0.1:{config.PORT}/docs)")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
