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


class ResearchLabFindingReviewSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class ResearchLabReportFields(BaseModel):
    titleOptionId: str | None = None
    severityOptionId: str | None = None
    likelihoodOptionId: str | None = None
    categoryOptionId: str | None = None
    rootCauseOptionId: str | None = None
    proofOfImpactOptionId: str | None = None
    recommendedMitigationOptionId: str | None = None
    verifiedEvidenceRefs: list[str] = Field(default_factory=list)
    optionalNotes: str | None = None


class ResearchLabReportSaveRequest(BaseModel):
    fields: ResearchLabReportFields
