"""CLI Runner for InsureMate Phase 4: Missing-Document Detection.

Usage:
    python run_phase4.py                     # Run default Phase-3 mock input
    python run_phase4.py --demo-discharge    # Run demonstration with Discharge Document missing
    python run_phase4.py --input <path>      # Run custom Phase-3 input JSON
    python run_phase4.py --check             # Check Ollama connection and model
"""
import sys
import json
import argparse
from pathlib import Path

from phase4.config import get_config
from phase4.gateway.ollama_client import OllamaClient
from phase4.detector import detect_missing_documents
from phase4.mock import load_phase3_sample


def print_banner():
    print("=" * 65)
    print("       INSUREMATE PHASE 4: MISSING-DOCUMENT DETECTION")
    print("=" * 65)


def check_ollama():
    config = get_config()
    print(f"Checking Ollama service at: {config.ollama_base_url}")
    print(f"Target model: {config.ollama_model}")
    client = OllamaClient(config=config)
    if client.is_available():
        print("[OK] Ollama service is reachable and responsive.")
    else:
        print("[ERROR] Cannot reach Ollama service. Please ensure Ollama is running.")
        sys.exit(1)


def display_results(result: dict):
    print("\n---------------- DETECTION RESULT ----------------")
    if "error" in result:
        print(f"[FAILED] Error: {result.get('error')}")
        print(f"Message: {result.get('message')}")
        print(f"Details: {json.dumps(result.get('details', {}), indent=2)}")
        return

    print(json.dumps(result, indent=2))
    print("\n---------------- SUMMARY TABLE -------------------")
    print(f"{'Sr':<4} | {'Document Title':<28} | {'Status':<10} | {'Page':<6}")
    print("-" * 56)
    for doc in result.get("missing_documents", []):
        status = "MISSING" if doc["missing"] else "PRESENT"
        page = str(doc["page_no"]) if doc["page_no"] is not None else "N/A"
        print(f"{doc['sr_no']:<4} | {doc['document_title']:<28} | {status:<10} | {page:<6}")
    print("-" * 56)


def main():
    parser = argparse.ArgumentParser(description="InsureMate Phase 4 Missing-Document Detector")
    parser.add_argument("--input", type=str, help="Path to Phase-3 JSON input file")
    parser.add_argument(
        "--demo-discharge",
        action="store_true",
        help="Demonstrate removing Discharge Document and verifying it is flagged missing"
    )
    parser.add_argument("--check", action="store_true", help="Check Ollama connection")

    args = parser.parse_args()

    print_banner()

    if args.check:
        check_ollama()
        return

    # Load data
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[ERROR] Input file not found: {input_path}")
            sys.exit(1)
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded Phase-3 input from: {input_path}")
    else:
        data = load_phase3_sample()
        print("Using temporary mock input from: phase4/mock/phase3_sample.json")

    if args.demo_discharge:
        print("\n[DEMO] Removing 'Patient Discharge Record' from submitted documents...")
        data["submitted_documents"] = [
            doc for doc in data["submitted_documents"]
            if "discharge" not in doc["document_title"].lower()
        ]

    config = get_config()
    print(f"Connecting to Ollama at {config.ollama_base_url} (model: {config.ollama_model})...")

    result = detect_missing_documents(data)
    display_results(result)


if __name__ == "__main__":
    main()
