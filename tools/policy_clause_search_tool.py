"""tools/policy_clause_search_tool.py
Policy Clause and Exclusion Search Tool for InsureMate.
Searches extracted insurance policy clauses, conditions, exclusions, waiting periods,
room rent caps, and benefits for specific user queries or insurance topics.
"""

import re
from typing import Any, Dict, List, Optional, Union
from tools.base_tool import AgentTool
from utils.logger import logger


class PolicyClauseSearchTool(AgentTool):
    """
    Callable Agent Tool: Policy Clause Search & Exclusion Inspector.
    Allows the InsureMate Agent to inspect specific terms, exclusions, and limits
    in a policy without needing to execute an entire claim preparation workflow.
    """

    name: str = "policy_clause_search_tool"
    description: str = (
        "Searches extracted policy clauses, conditions, exclusions, waiting periods, "
        "and benefits for specific user queries, topics, or claim scenarios."
    )

    @property
    def schema(self) -> Dict[str, Any]:
        """JSON schema definition for LLM tool calling registration."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific query, topic, or clause to search for (e.g. 'cataract surgery limit', 'pre-existing disease waiting period', 'exclusions').",
                        },
                        "policy_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Optional list of extracted policy document pages. If omitted, uses extracted_data.",
                        },
                        "extracted_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Complete list of extracted document pages from document_extraction.",
                        },
                        "claim_id": {
                            "type": "string",
                            "description": "Optional claim ID context.",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized Phase 6 execution method."""
        validated = self.validate_input(input_data)
        query = str(validated.get("query") or validated.get("topic") or "").strip()
        policy_data = validated.get("policy_data")
        extracted_data = validated.get("extracted_data")

        return self.run(query=query, policy_data=policy_data, extracted_data=extracted_data)

    def run(
        self,
        query: str,
        policy_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
        extracted_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Core execution logic searching policy clauses and text."""
        if not query:
            return {
                "status": "error",
                "error": "Query parameter cannot be empty.",
                "matched_clauses": [],
                "summary": "Search failed: no search query provided.",
            }

        # Gather target pages
        pages: List[Dict[str, Any]] = []
        if policy_data:
            if isinstance(policy_data, list):
                pages.extend(policy_data)
            elif isinstance(policy_data, dict):
                pages.append(policy_data)

        if not pages and extracted_data:
            pages = [
                d for d in extracted_data
                if d.get("document_type") == "insurance_policy" or d.get("policy_clauses")
            ]
            if not pages:
                pages = extracted_data

        if not pages:
            return {
                "status": "warning",
                "query": query,
                "matched_clauses": [],
                "summary": "No policy document records found to search. Please extract documents first.",
            }

        query_terms = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
        matched_items: List[Dict[str, Any]] = []

        for page in pages:
            page_no = page.get("page_number", 1)
            clauses = page.get("policy_clauses", []) or []
            conditions = page.get("relevant_conditions", []) or []
            rel_text = str(page.get("policy_relevant_text") or "")
            summary_text = str(page.get("extracted_text_summary") or "")

            all_candidates = []
            for c in clauses:
                all_candidates.append(("policy_clause", str(c)))
            for c in conditions:
                all_candidates.append(("condition", str(c)))
            if rel_text:
                all_candidates.append(("policy_text", rel_text))
            if summary_text:
                all_candidates.append(("summary", summary_text))

            for source_type, text in all_candidates:
                lower_text = text.lower()
                score = 0
                for term in query_terms:
                    if term in lower_text:
                        score += 1

                # If query matched or broad search for clauses/conditions
                if score > 0 or not query_terms:
                    matched_items.append({
                        "page_number": page_no,
                        "source_type": source_type,
                        "clause_text": text,
                        "relevance_score": score,
                    })

        # Sort by relevance score descending
        matched_items.sort(key=lambda x: x["relevance_score"], reverse=True)

        if matched_items:
            best_match = matched_items[0]
            summary = (
                f"Found {len(matched_items)} matching clause(s) for '{query}' "
                f"on page(s) {sorted(list(set(m['page_number'] for m in matched_items)))}. "
                f"Primary excerpt: {best_match['clause_text'][:120]}..."
            )
            verdict = "MATCH_FOUND"
        else:
            summary = f"No explicit policy clauses found matching '{query}' in the submitted policy pages."
            verdict = "NO_MATCH"

        logger.info(f"[POLICY CLAUSE SEARCH] Query: '{query}' -> {verdict} ({len(matched_items)} matches)")

        return {
            "status": "success",
            "query": query,
            "verdict": verdict,
            "total_matches": len(matched_items),
            "matched_clauses": matched_items[:5],
            "summary": summary,
        }
