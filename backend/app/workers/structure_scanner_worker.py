"""Local polling handoff for asynchronous document structure scanning.

The API performs scanning synchronously today. This worker provides the
reference project's Phase 1 handoff contract for deployments that want to
move scans out of request handling later.
"""

from __future__ import annotations

import time

from app.config import settings
from app.database import list_all_documents


def pending_documents() -> list[dict]:
    """Return documents waiting for a scanner job in the local tenant."""
    return [
        document
        for document in list_all_documents(settings.dev_tenant_id)
        if document.get("workflow_state") in {"pending_review", "needs_attention"}
    ]


def run_polling_worker(interval_seconds: int = 10) -> None:
    """Poll local SQLite and emit scanner handoff jobs until interrupted."""
    print("DocFlow Structure Scanner worker started")
    while True:
        for document in pending_documents():
            print(
                f"scanner handoff: {document['document_id']} "
                f"({document['filename']}) state={document['workflow_state']}"
            )
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_polling_worker()
