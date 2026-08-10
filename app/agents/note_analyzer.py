"""AI-driven analysis of SAP Notes.

Uses the configured LLM to:

  * Summarize business + technical impact
  * Propose an implementation sequence honoring prerequisites
  * Predict conflicts
  * Recommend additional prerequisite notes
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..llm.base import LLMClient
from ..models.execution import ExecutionRecord, ImplementationLog, SystemType
from ..models.sap_note import NoteAnalysisResult


_SYSTEM_PROMPT = (
    "You are a Senior SAP Solution Architect specialising in CVI (Customer "
    "Vendor Integration) and MDS (Master Data Synchronization). "
    "Given a set of SAP Notes and target system, produce a concise, "
    "structured markdown analysis with the sections: "
    "Executive Summary, Business Impact, Technical Impact, "
    "Implementation Sequence, Dependencies, Predicted Conflicts, "
    "Recommended Prerequisite Notes."
)


class NoteAnalyzerAgent:
    name = "NoteAnalyzer"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    # ------------------------------------------------------------------
    def _build_prompt(self, record: ExecutionRecord) -> str:
        lines: list[str] = []
        sys_label = "S/4HANA (MDS_LOAD_COCKPIT)" if record.system_type == SystemType.S4HANA else "ECC (CVI_COCKPIT)"
        lines.append(f"Target system: {sys_label}")
        lines.append(f"System tier: {record.system_tier.value}")
        if record.user_prompt:
            lines.append(f"\nUser prompt / context:\n{record.user_prompt}\n")
        lines.append("\nSAP Notes under review:")
        for meta in record.metadata:
            lines.append(
                f"- {meta.note_number}: {meta.title or '(no title)'} | "
                f"component={meta.component or 'n/a'} | "
                f"status={meta.release_status} | "
                f"prereqs={','.join(meta.prerequisites) or 'none'} | "
                f"conflicts={','.join(meta.conflicts) or 'none'}"
            )
        lines.append(
            "\nProduce the structured analysis. Keep it under 400 lines. "
            "Bulleted lists preferred."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _parse(self, text: str, record: ExecutionRecord) -> NoteAnalysisResult:
        # Very forgiving section parser.
        sections: dict[str, list[str]] = {}
        current = "executive_summary"
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = re.match(r"^#{1,3}\s*(.+?)\s*$", line)
            if m:
                header = m.group(1).lower()
                if "business" in header and "impact" in header:
                    current = "business_impact"
                elif "technical" in header and "impact" in header:
                    current = "technical_impact"
                elif "implementation" in header and "sequence" in header:
                    current = "implementation_sequence"
                elif "dependenc" in header:
                    current = "dependencies"
                elif "predicted" in header or ("conflict" in header and "recommend" not in header):
                    current = "predicted_conflicts"
                elif "prereq" in header or "recommended" in header:
                    current = "recommended_prereqs"
                elif "executive" in header or "summary" in header:
                    current = "executive_summary"
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)

        def _joined(key: str) -> str:
            return "\n".join(sections.get(key, [])).strip()

        def _bullets(key: str) -> list[str]:
            out: list[str] = []
            for ln in sections.get(key, []):
                if ln.startswith(("-", "*", "•")):
                    out.append(ln.lstrip("-*• ").strip())
                elif re.match(r"^\d+[.)]\s", ln):
                    out.append(re.sub(r"^\d+[.)]\s", "", ln).strip())
            return out

        return NoteAnalysisResult(
            executive_summary=_joined("executive_summary"),
            business_impact=_joined("business_impact"),
            technical_impact=_joined("technical_impact"),
            implementation_sequence=_bullets("implementation_sequence")
            or [m.note_number for m in record.metadata],
            dependencies=_bullets("dependencies"),
            predicted_conflicts=_bullets("predicted_conflicts"),
            recommended_prereqs=_bullets("recommended_prereqs"),
            raw_llm_text=text,
            llm_provider=self.llm.provider_name,
        )

    # ------------------------------------------------------------------
    def run(self, record: ExecutionRecord) -> NoteAnalysisResult:
        prompt = self._build_prompt(record)
        resp: Any = self.llm.complete(prompt, system=_SYSTEM_PROMPT)
        analysis = self._parse(resp.text, record)
        record.analysis = analysis

        # Emit an execution-log entry so users can see the real LLM was
        # called (provider + latency), without leaking prompt/response.
        record.logs.append(
            ImplementationLog(
                ts=datetime.now(timezone.utc).isoformat(),
                step="analyze",
                level="INFO",
                message=(
                    f"[NoteAnalyzer] LLM analysis complete via '{resp.provider}' "
                    f"(model={resp.model}, latency={resp.latency_ms}ms)"
                ),
                detail={
                    "provider": resp.provider,
                    "model": resp.model,
                    "latency_ms": resp.latency_ms,
                    "chars": len(resp.text or ""),
                },
            )
        )
        return analysis
