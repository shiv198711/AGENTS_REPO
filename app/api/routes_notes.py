"""SAP Note upload / validate / analyze / implement endpoints."""
from __future__ import annotations

import json
import queue
import re
import shutil
import threading
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from ..agents.orchestrator import Orchestrator
from ..config import get_settings
from ..exporters.report_exporter import ReportExporter
from ..llm.factory import build_llm
from ..models.audit import AuditAction
from ..models.execution import (
    ExecutionRecord,
    ImplementationLog,
    ImplementationRequest,
    SystemTier,
    SystemType,
)
from ..models.sap_note import SAPNoteInput
from ..storage.audit_store import get_audit_store
from ..storage.job_store import get_job_store


router = APIRouter(prefix="/notes", tags=["notes"])

_NOTE_RE = re.compile(r"(\d{6,10})")


class NoteUploadResponse(BaseModel):
    upload_id: str
    files: list[str]
    parsed_notes: list[SAPNoteInput]


class ValidateRequest(BaseModel):
    system_type: SystemType
    system_tier: SystemTier = SystemTier.DEV
    notes: list[SAPNoteInput]
    requested_by: str = "anonymous"


class AnalyzeRequest(BaseModel):
    system_type: SystemType
    system_tier: SystemTier = SystemTier.DEV
    notes: list[SAPNoteInput]
    user_prompt: str = ""
    requested_by: str = "anonymous"


class ImplementResponse(BaseModel):
    execution_id: str
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Upload — accepts multiple files, extracts note numbers from filename/content
# --------------------------------------------------------------------------
@router.post("/upload", response_model=NoteUploadResponse)
async def upload_notes(files: list[UploadFile] = File(...)) -> NoteUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    settings = get_settings()
    upload_id = uuid.uuid4().hex[:10]
    target = settings.uploads_path / upload_id
    target.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    parsed: list[SAPNoteInput] = []
    for f in files:
        name = f.filename or f"upload-{uuid.uuid4().hex[:6]}"
        dest = target / name
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        saved.append(str(dest.relative_to(settings.data_path)))

        note_numbers = _NOTE_RE.findall(name)
        try:
            body = dest.read_text("utf-8", errors="ignore")
            note_numbers.extend(_NOTE_RE.findall(body))
        except Exception:  # noqa: BLE001
            pass
        for n in dict.fromkeys(note_numbers):
            parsed.append(
                SAPNoteInput(
                    note_number=n,
                    title=name,
                    source="upload",
                    attachments=[str(dest.relative_to(settings.data_path))],
                )
            )

    get_audit_store().log(
        AuditAction.NOTE_UPLOAD,
        actor="anonymous",
        detail={"upload_id": upload_id, "files": saved, "count": len(parsed)},
    )
    return NoteUploadResponse(upload_id=upload_id, files=saved, parsed_notes=parsed)


# --------------------------------------------------------------------------
# Validate only (no implementation)
# --------------------------------------------------------------------------
@router.post("/validate")
def validate_notes(body: ValidateRequest) -> dict[str, Any]:
    llm = build_llm()
    orch = Orchestrator(llm)
    record = orch.new_record(
        ImplementationRequest(
            system_type=body.system_type,
            system_tier=body.system_tier,
            notes=body.notes,
            requested_by=body.requested_by,
        )
    )
    from ..agents.note_validator import NoteValidatorAgent
    from ..connectors.rfc_connector import build_rfc_connector

    rfc = build_rfc_connector(body.system_type.value)
    with rfc:
        NoteValidatorAgent(rfc, orch.rbac).run(record)
    orch.jobs.save(record)
    return {
        "execution_id": record.execution_id,
        "system_type": record.system_type.value,
        "validation": [v.model_dump() for v in record.validation],
        "metadata": [m.model_dump() for m in record.metadata],
    }


# --------------------------------------------------------------------------
# Analyze only (LLM)
# --------------------------------------------------------------------------
@router.post("/analyze")
def analyze_notes(body: AnalyzeRequest) -> dict[str, Any]:
    llm = build_llm()
    orch = Orchestrator(llm)
    record = orch.new_record(
        ImplementationRequest(
            system_type=body.system_type,
            system_tier=body.system_tier,
            notes=body.notes,
            user_prompt=body.user_prompt,
            requested_by=body.requested_by,
        )
    )
    from ..agents.note_analyzer import NoteAnalyzerAgent
    from ..agents.note_validator import NoteValidatorAgent
    from ..connectors.rfc_connector import build_rfc_connector

    rfc = build_rfc_connector(body.system_type.value)
    with rfc:
        NoteValidatorAgent(rfc, orch.rbac).run(record)
    NoteAnalyzerAgent(llm).run(record)
    orch.jobs.save(record)
    return {
        "execution_id": record.execution_id,
        "analysis": record.analysis.model_dump() if record.analysis else None,
        "validation": [v.model_dump() for v in record.validation],
    }


# --------------------------------------------------------------------------
# Implement (full orchestration, blocking)
# --------------------------------------------------------------------------
@router.post("/implement", response_model=ImplementResponse)
def implement_notes(
    body: ImplementationRequest,
    release_transports: bool = Query(False, description="Release transports if authorized"),
) -> ImplementResponse:
    llm = build_llm()
    orch = Orchestrator(llm)
    record = orch.run(body, release_transports=release_transports)
    return ImplementResponse(
        execution_id=record.execution_id,
        status=record.status.value,
        summary=ReportExporter().summary(record),
    )


# --------------------------------------------------------------------------
# Implement — live SSE stream
# --------------------------------------------------------------------------
# The orchestrator runs on a background thread; every ImplementationLog
# entry it appends to the ExecutionRecord is forwarded to the SSE client
# via a queue. When the orchestrator finishes we push a `done` frame.
# --------------------------------------------------------------------------
class _StreamingLogList(list):
    """A `list` subclass that forwards every append() to a queue.

    Used to shadow ``ExecutionRecord.logs`` so agents can keep calling
    ``record.logs.append(...)`` while the UI receives live frames.
    """

    def __init__(self, q: "queue.Queue[dict[str, Any]]") -> None:
        super().__init__()
        self._q = q

    def append(self, item: ImplementationLog) -> None:  # type: ignore[override]
        super().append(item)
        try:
            self._q.put_nowait(
                {
                    "type": "log",
                    "ts": item.ts,
                    "level": item.level,
                    "step": item.step,
                    "message": item.message,
                }
            )
        except Exception:  # noqa: BLE001
            pass


@router.post("/implement/stream")
def implement_stream(
    body: ImplementationRequest,
    release_transports: bool = Query(False),
):
    """Server-Sent-Events stream — live progress from the orchestrator."""
    q: "queue.Queue[dict[str, Any]]" = queue.Queue()

    def _run_orch() -> None:
        try:
            llm = build_llm()
            q.put_nowait({"type": "start", "provider": llm.provider_name})
            orch = Orchestrator(llm)
            # Wrap the record's logs list so appends are forwarded live.
            original_new = orch.new_record

            def _wrapped_new(request: ImplementationRequest) -> ExecutionRecord:
                rec = original_new(request)
                streaming_logs = _StreamingLogList(q)
                # Migrate any pre-existing logs
                for lg in rec.logs:
                    streaming_logs.append(lg)
                rec.logs = streaming_logs  # type: ignore[assignment]
                return rec

            orch.new_record = _wrapped_new  # type: ignore[assignment]
            record = orch.run(body, release_transports=release_transports)
            q.put_nowait(
                {
                    "type": "done",
                    "execution_id": record.execution_id,
                    "summary": ReportExporter().summary(record),
                }
            )
        except Exception as exc:  # noqa: BLE001
            q.put_nowait({"type": "error", "message": str(exc)})
        finally:
            q.put_nowait({"type": "__end__"})

    thread = threading.Thread(target=_run_orch, daemon=True)
    thread.start()

    def _iter():
        while True:
            frame = q.get()  # blocks until a frame is available
            if frame.get("type") == "__end__":
                return
            yield f"data: {json.dumps(frame)}\n\n"

    return StreamingResponse(_iter(), media_type="text/event-stream")


# --------------------------------------------------------------------------
# Download report
# --------------------------------------------------------------------------
@router.get("/{execution_id}/report")
def download_report(execution_id: str, fmt: str = Query("md", pattern="^(md|json|docx)$")):
    record = get_job_store().get(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    exp = ReportExporter()
    if fmt == "md":
        return PlainTextResponse(exp.markdown(record), media_type="text/markdown")
    if fmt == "json":
        return PlainTextResponse(exp.json(record), media_type="application/json")
    return Response(
        content=exp.docx(record),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="cvi_mds_{execution_id}.docx"'
        },
    )