from typing import List, Optional, Literal
from enum import Enum
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()

class Tone(str, Enum):
    DRY = "dry"
    WHOLESOME = "wholesome"
    SAVAGE = "savage"
    ABSURDIST = "absurdist"
    NEUTRAL = "neutral"

class Audience(str, Enum):
    GENERAL = "general"
    TECH = "tech"
    FINANCE = "finance"
    SPORTS = "sports"

class SafetyMode(str, Enum):
    STRICT = "strict"
    STANDARD = "standard"

class RenderConfig(BaseModel):
    size: Literal[512, 768, 1024] = 768
    format: Literal["png", "jpg", "webp"] = "png"
    watermark: bool = True

class TemplateFilters(BaseModel):
    include_tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None
    template_ids: Optional[List[str]] = None
    format: Optional[Literal["single", "two-panel", "four-panel", "caption-only"]] = None

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

class MemeScores(BaseModel):
    humor: float
    relevance: float
    clarity: float
    safety: float
    originality: float

class MemeCandidate(BaseModel):
    candidate_id: str
    template_id: str
    template_name: str
    captions: List[str]
    image_url: str
    alt_text: Optional[str] = None
    explanation: Optional[str] = None
    scores: MemeScores
    citations: Optional[List[str]] = None

class MemeGenerateResponse(BaseModel):
    trace_id: str
    candidates: List[MemeCandidate]
    warnings: Optional[List[str]] = None
