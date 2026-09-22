"""
Table extractor and parser for billing tables, lab reports, and grid structures.
Supports pre-extracted tables from Phase 1 as well as heuristic columnar text parsing.
"""

import re
from typing import List, Tuple, Optional
from ..schemas.output_schema import ExtractedTable, TableRow, TableCell, ItemizedCharge
from ..schemas.input_schema import RawPageInput, RawTableInput
from ..schemas.common import ConfidenceLevel
from ..provenance.tracer import ProvenanceTracer
from ..normalization.amount_normalizer import normalize_amount_string


class TableExtractor:
    """Extracts tables and itemized charges from pages."""

    @classmethod
    def extract_tables(
        cls,
        document_id: str,
        pages: List[RawPageInput]
    ) -> Tuple[List[ExtractedTable], List[ItemizedCharge]]:
        tables: List[ExtractedTable] = []
        itemized_charges: List[ItemizedCharge] = []
        table_counter = 1

        for page in pages:
            # 1. Process tables supplied directly by Phase 1
            if page.tables:
                for raw_tbl in page.tables:
                    extracted_tbl, charges = cls._process_raw_table(
                        document_id, page.page_number, raw_tbl, f"tbl_{document_id}_p{page.page_number}_{table_counter}"
                    )
                    tables.append(extracted_tbl)
                    itemized_charges.extend(charges)
                    table_counter += 1

            # 2. If no tables provided by Phase 1, attempt heuristic table detection from text
            if not page.tables:
                text_tables, text_charges = cls._detect_tables_from_text(
                    document_id, page, table_counter
                )
                tables.extend(text_tables)
                itemized_charges.extend(text_charges)
                table_counter += len(text_tables)

        return tables, itemized_charges

    @classmethod
    def _process_raw_table(
        cls,
        document_id: str,
        page_number: int,
        raw_table: RawTableInput,
        table_id: str
    ) -> Tuple[ExtractedTable, List[ItemizedCharge]]:
        rows = raw_table.rows
        headers: List[str] = []
        parsed_rows: List[TableRow] = []
        itemized_charges: List[ItemizedCharge] = []

        if not rows:
            return ExtractedTable(
                table_id=table_id,
                page_number=page_number,
                headers=[],
                rows=[],
                row_count=0,
                col_count=0,
                quality_notes="Empty table"
            ), []

        # First row is typically headers
        headers = [c.strip() for c in rows[0]]
        col_count = len(headers)

        # Identify column roles (description, qty, rate, amount)
        desc_idx, qty_idx, rate_idx, amt_idx = cls._identify_column_indices(headers)

        for r_idx, row_cells in enumerate(rows[1:], start=1):
            cell_objs: List[TableCell] = []
            for c_idx, cell_text in enumerate(row_cells):
                cell_objs.append(TableCell(
                    text=cell_text.strip(),
                    column_index=c_idx,
                    row_index=r_idx,
                ))
            parsed_rows.append(TableRow(
                cells=cell_objs,
                raw_row_text=" | ".join(row_cells)
            ))

            # Extract itemized charge if columns matched
            if desc_idx is not None and amt_idx is not None and len(row_cells) > max(desc_idx, amt_idx):
                desc = row_cells[desc_idx].strip()
                amt_str = row_cells[amt_idx].strip()
                amt_val, _, _, _ = normalize_amount_string(amt_str)

                # Optional qty and rate
                qty_val = None
                if qty_idx is not None and len(row_cells) > qty_idx:
                    try:
                        qty_val = float(re.sub(r"[^\d\.]", "", row_cells[qty_idx]))
                    except (ValueError, TypeError):
                        pass

                rate_val = None
                if rate_idx is not None and len(row_cells) > rate_idx:
                    r_val, _, _, _ = normalize_amount_string(row_cells[rate_idx])
                    rate_val = r_val

                if desc and amt_val is not None:
                    # Avoid capturing totals/subtotals as itemized charges
                    if not re.search(r"\b(total|subtotal|gross|net|tax|gst)\b", desc, re.IGNORECASE):
                        prov = ProvenanceTracer.create_provenance(
                            document_id=document_id,
                            page_number=page_number,
                            source_text=" | ".join(row_cells),
                            extraction_method="phase1_table_matrix",
                            confidence=ConfidenceLevel.HIGH,
                            confidence_score=0.95,
                        )
                        itemized_charges.append(ItemizedCharge(
                            description=desc,
                            quantity=qty_val,
                            unit_price=rate_val,
                            amount=amt_val,
                            provenance=prov,
                        ))

        return ExtractedTable(
            table_id=table_id,
            page_number=page_number,
            headers=headers,
            rows=parsed_rows,
            row_count=len(parsed_rows),
            col_count=col_count,
            bounding_box=raw_table.bbox,
            extraction_method="phase1_table_input",
            quality_notes=None if col_count > 0 else "Unclear columns",
        ), itemized_charges

    @classmethod
    def _detect_tables_from_text(
        cls,
        document_id: str,
        page: RawPageInput,
        start_id_num: int
    ) -> Tuple[List[ExtractedTable], List[ItemizedCharge]]:
        """
        Detects tables formatted in text (e.g. pipe-delimited or multi-column text).
        """
        tables: List[ExtractedTable] = []
        itemized_charges: List[ItemizedCharge] = []
        lines = page.raw_text.split("\n")

        # Collect contiguous blocks that look like table rows (contain pipes or 2+ aligned columns)
        current_block: List[List[str]] = []
        table_idx = start_id_num

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                if len(current_block) >= 2:
                    tbl, charges = cls._build_table_from_text_block(
                        document_id, page.page_number, current_block, f"tbl_{document_id}_p{page.page_number}_{table_idx}"
                    )
                    if tbl:
                        tables.append(tbl)
                        itemized_charges.extend(charges)
                        table_idx += 1
                current_block = []
                continue

            # Pipe separated
            if "|" in trimmed and len(trimmed.split("|")) >= 3:
                cells = [c.strip() for c in trimmed.split("|") if c.strip() != ""]
                if len(cells) >= 2:
                    current_block.append(cells)
                continue

            # Space separated (3 or more spaces between columns, at least 3 columns)
            cols = [c.strip() for c in re.split(r"\s{3,}", trimmed) if c.strip()]
            if len(cols) >= 3:
                current_block.append(cols)
            else:
                if len(current_block) >= 2:
                    tbl, charges = cls._build_table_from_text_block(
                        document_id, page.page_number, current_block, f"tbl_{document_id}_p{page.page_number}_{table_idx}"
                    )
                    if tbl:
                        tables.append(tbl)
                        itemized_charges.extend(charges)
                        table_idx += 1
                current_block = []

        if len(current_block) >= 2:
            tbl, charges = cls._build_table_from_text_block(
                document_id, page.page_number, current_block, f"tbl_{document_id}_p{page.page_number}_{table_idx}"
            )
            if tbl:
                tables.append(tbl)
                itemized_charges.extend(charges)

        return tables, itemized_charges

    @classmethod
    def _build_table_from_text_block(
        cls,
        document_id: str,
        page_number: int,
        block_rows: List[List[str]],
        table_id: str
    ) -> Tuple[Optional[ExtractedTable], List[ItemizedCharge]]:
        if not block_rows:
            return None, []

        raw_tbl = RawTableInput(
            page_number=page_number,
            rows=block_rows,
        )
        tbl, charges = cls._process_raw_table(document_id, page_number, raw_tbl, table_id)
        tbl.extraction_method = "text_layout_heuristic"
        return tbl, charges

    @staticmethod
    def _identify_column_indices(headers: List[str]) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """
        Identifies column indices for: (description, quantity, rate, amount).
        """
        desc_idx, qty_idx, rate_idx, amt_idx = None, None, None, None
        for idx, h in enumerate(headers):
            h_low = h.lower()
            if re.search(r"\b(description|item|particulars?|service|procedure|test|investigation)\b", h_low):
                desc_idx = idx
            elif re.search(r"\b(qty|quantity|units?|count)\b", h_low):
                qty_idx = idx
            elif re.search(r"\b(rate|price|unit\s*price|cost)\b", h_low):
                rate_idx = idx
            elif re.search(r"\b(amount|total|net\s*amount|charges?)\b", h_low):
                amt_idx = idx

        return desc_idx, qty_idx, rate_idx, amt_idx
