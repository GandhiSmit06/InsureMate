"""Convenience runner script for InsureMate Phase 3 server."""

import sys
from pathlib import Path

# Add current directory and InsureMate to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Auto-delegate to .venv if current interpreter lacks dependencies and .venv exists
_venv_python = root_dir / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    try:
        import paddle  # type: ignore
    except ImportError:
        import subprocess
        _res = subprocess.run([str(_venv_python)] + sys.argv)
        sys.exit(_res.returncode)

import uvicorn
from AI.requirement_extraction.main import app
from AI.requirement_extraction.config import config

if __name__ == "__main__":
    print(f"Starting InsureMate Phase 3 on http://127.0.0.1:{config.PORT}")
    print(f"Swagger API Docs: http://localhost:{config.PORT}/docs (or http://127.0.0.1:{config.PORT}/docs)")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
