"""Safe file operations via operation journal (quarantine, never os.remove)."""
from __future__ import annotations

from operation_journal import OperationJournal


class FileOperationService:
    def __init__(self, journal: OperationJournal) -> None:
        self.journal = journal

    def delete(self, path: str) -> tuple[bool, str]:
        """Move file to quarantine via journal. Never calls os.remove."""
        return self.journal.record_delete(path)
