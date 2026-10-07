"""Mock data module for InsureMate Phase 4."""
from pathlib import Path
import json

MOCK_DIR = Path(__file__).parent
PHASE3_SAMPLE_PATH = MOCK_DIR / "phase3_sample.json"


def load_phase3_sample() -> dict:
    """Load the default Phase 3 mock sample data."""
    with open(PHASE3_SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
