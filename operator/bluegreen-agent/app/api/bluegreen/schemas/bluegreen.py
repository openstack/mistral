from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class NamespaceInfo(BaseModel):
    name: str
    state: str
    version: Optional[str] = None


class BGState(BaseModel):
    controllerNamespace: str
    originNamespace: NamespaceInfo
    peerNamespace: NamespaceInfo
    updateTime: datetime


class BluegreenRequest(BaseModel):
    BGState: BGState


class SyncResponse(BaseModel):
    status: Optional[str] = None
    message: str
    operationDetails: Optional[Any] = None


class ErrorResponse(BaseModel):
    id: str
    reason: str
    message: Optional[str] = None
    status: int
    meta: Optional[Dict[str, Any]] = None
    code: Optional[str] = None
    referenceError: Optional[str] = None
    type: str = Field("NC.TMFErrorResponse.v1.0", alias="@type")
