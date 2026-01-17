from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter

from src.api.routes.meme.models import (
    Tone,
    Audience,
    SafetyMode,
    RenderConfig,
    TemplateFilters,
    MemeCandidate,
)

router = APIRouter()

class MemeGenerateRequest(BaseModel):
    prompt: str
    url: Optional[str] = None
    num_candidates: int = 10
    tone: Optional[Tone] = None
    audience: Optional[Audience] = None
    style: Optional[str] = None
    safety_mode: SafetyMode = SafetyMode.STANDARD
    template_filters: Optional[TemplateFilters] = None
    render: Optional[RenderConfig] = None
    language: str = "en"

class MemeGenerateResponse(BaseModel):
    trace_id: str
    candidates: List[MemeCandidate]
    warnings: Optional[List[str]] = None
