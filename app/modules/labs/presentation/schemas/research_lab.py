from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchLabAPIResponse(BaseModel):
    success: bool = True
    data: Any
    error: Any = None


class ResearchLabFilePatch(BaseModel):
    path: str
    content: str


class ResearchLabPatchFilesRequest(BaseModel):
    files: list[ResearchLabFilePatch] = Field(min_length=1)


class ResearchLabTerminalQuery(BaseModel):
    after_sequence: int | None = None


class ResearchLabTransactionRequest(BaseModel):
    action_type: str
    parameters: dict = Field(default_factory=dict)


class ResearchLabVerifyObjectiveRequest(BaseModel):
    objective_ref: str | None = None


class ResearchLabReportFields(BaseModel):
    vulnerability_category: str | None = None
    affected_area: str | None = None
    attacker_controlled_input: str | None = None
    root_cause: str = ""
    impact: str = ""
    proof: str = ""
    recommended_fix: str = ""
    severity: str | None = None


class ResearchLabReportSaveRequest(BaseModel):
    fields: ResearchLabReportFields
