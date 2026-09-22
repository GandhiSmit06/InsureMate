from abc import ABC, abstractmethod
from typing import List, Optional
from ..schema.models import PageText, RequirementItem


class BaseExtractor(ABC):
    """Abstract base class for requirement extractors."""

    @abstractmethod
    def extract(
        self,
        pages: List[PageText],
        claim_type: Optional[str] = None,
    ) -> List[RequirementItem]:
        """Extract insurance claim requirements from page texts.

        Args:
            pages: List of PageText objects with page numbers and text.
            claim_type: Optional claim context ('hospitalization', 'cashless', etc.).

        Returns:
            List of RequirementItem instances.
        """
        pass
