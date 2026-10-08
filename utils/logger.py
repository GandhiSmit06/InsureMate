"""
utils/logger.py
Standardized technical logger for InsureMate.
Emits concise operational tags: [PDF], [QWEN-VL], [CLASSIFIER], [VALIDATION], [VALIDITY], [RESULT].
"""

import sys


class InsureLogger:
    """Concise operational logger for InsureMate services and tools."""

    @staticmethod
    def pdf(msg: str) -> None:
        print(f"[PDF] {msg}")

    @staticmethod
    def qwen_vl(msg: str) -> None:
        print(f"[QWEN-VL] {msg}")

    @staticmethod
    def classifier(msg: str) -> None:
        print(f"[CLASSIFIER] {msg}")

    @staticmethod
    def validation(msg: str) -> None:
        print(f"[VALIDATION] {msg}")

    @staticmethod
    def validity(msg: str) -> None:
        print(f"[VALIDITY] {msg}")

    @staticmethod
    def missing_doc(msg: str) -> None:
        print(f"[MISSING-DOC] {msg}")

    @staticmethod
    def llm(msg: str) -> None:
        print(f"[LLM] {msg}")

    @staticmethod
    def result(msg: str) -> None:
        print(f"[RESULT] {msg}")

    @staticmethod
    def info(msg: str) -> None:
        print(msg)

    @staticmethod
    def tool(msg: str) -> None:
        print(f"[TOOL] {msg}")

    @staticmethod
    def error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)


logger = InsureLogger()
