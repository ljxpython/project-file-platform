from __future__ import annotations

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    project_id: str
    path: str = "/"
    filename: str
    total_size: int = Field(ge=0)
    chunk_size: int = Field(ge=1)


class UploadInitResponse(BaseModel):
    upload_id: str


class UploadCompleteRequest(BaseModel):
    upload_id: str
    parts: list[int]


class UploadAbortRequest(BaseModel):
    upload_id: str
