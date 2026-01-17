# Implementation Plan: Context-Aware Meme Generator API

## Overview

This plan outlines the implementation of the Context-Aware Meme Generator API based on the PRD. The implementation follows a phased approach, starting with core functionality and progressively adding complexity.

## Phase 0: Foundation & Prompt-Only Generation

### Goal
Establish basic API infrastructure and generate memes from text prompts without URL context.

### 0.1 Project Setup & Configuration

**Config additions to `global_config.yaml`:**
```yaml
meme_generator:
  default_num_candidates: 10
  max_candidates: 25
  default_timeout: 25
  default_render_size: 768
  default_render_format: "png"

  # Performance targets
  prompt_only_p50_target: 8
  url_based_p50_target: 15

  # Cost controls
  max_web_sources: 5
  max_templates_per_request: 50

llm_providers:
  google_nano_banana:
    api_key_env: "GOOGLE_NANO_BANANA_API_KEY"
    base_url: "https://api.google.com/nano-banana-pro/v1"
    default_model: "nano-banana-pro-1"

  openai_web_search:
    api_key_env: "OPENAI_API_KEY"
    model: "gpt-4-turbo-preview"
    enable_web_search: true

logo_service:
  base_url: "https://api.logo.dev/v1"
  api_key_env: "LOGO_DEV_API_KEY"
  cache_ttl: 3600

object_storage:
  provider: "s3"  # or "local" for dev
  bucket: "memegen-outputs"
  region: "us-east-1"
  signed_url_expiry: 3600

ranking:
  weights:
    relevance: 0.3
    humor: 0.25
    clarity: 0.2
    originality: 0.15
    safety: 0.1

  allow_per_request_override: true

safety:
  default_mode: "standard"
  strict_mode_templates: []
  blocked_tags: ["nsfw", "explicit", "hate"]
```

**Environment variables in `.env`:**
```
GOOGLE_NANO_BANANA_API_KEY=...
OPENAI_API_KEY=...
LOGO_DEV_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### 0.2 Database Schema

**Create Alembic migration for templates table:**

```python
# alembic/versions/001_create_templates.py

def upgrade():
    # Main templates table
    op.create_table(
        'templates',
        sa.Column('template_id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('image_uri', sa.String(500), nullable=False),
        sa.Column('format', sa.Enum('single', 'two-panel', 'four-panel', 'multi-panel', 'freeform', name='template_format'), nullable=False),
        sa.Column('text_boxes', sa.JSON, nullable=True),  # Optional: coords, max_chars, alignment
        sa.Column('tags', sa.ARRAY(sa.String), nullable=True),
        sa.Column('tone_affinity', sa.ARRAY(sa.String), nullable=True),
        sa.Column('safety_flags', sa.ARRAY(sa.String), nullable=True),
        sa.Column('example_captions', sa.JSON, nullable=True),
        sa.Column('constraints', sa.JSON, nullable=True),  # max text length, avoid topics
        sa.Column('external_assets', sa.JSON, nullable=True),  # logo requirements
        sa.Column('license', sa.String(100), nullable=False),
        sa.Column('attribution', sa.String(500), nullable=True),
        sa.Column('embedding', sa.ARRAY(sa.Float), nullable=True),  # Vector embedding
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Indices
    op.create_index('idx_templates_tags', 'templates', ['tags'], postgresql_using='gin')
    op.create_index('idx_templates_format', 'templates', ['format'])

    # Meme candidates table (for caching/retrieval)
    op.create_table(
        'meme_candidates',
        sa.Column('candidate_id', sa.String(50), primary_key=True),
        sa.Column('trace_id', sa.String(50), nullable=False),
        sa.Column('template_id', sa.String(50), sa.ForeignKey('templates.template_id')),
        sa.Column('captions', sa.JSON, nullable=False),
        sa.Column('image_uri', sa.String(500), nullable=True),
        sa.Column('alt_text', sa.String(500), nullable=True),
        sa.Column('explanation', sa.Text, nullable=True),
        sa.Column('scores', sa.JSON, nullable=False),  # humor, relevance, etc.
        sa.Column('citations', sa.JSON, nullable=True),
        sa.Column('request_params', sa.JSON, nullable=False),  # Original request
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('idx_candidates_trace', 'meme_candidates', ['trace_id'])

    # Request logs table
    op.create_table(
        'request_logs',
        sa.Column('trace_id', sa.String(50), primary_key=True),
        sa.Column('prompt', sa.Text, nullable=True),  # Nullable for privacy opt-out
        sa.Column('url', sa.String(1000), nullable=True),
        sa.Column('url_fetch_status', sa.String(50), nullable=True),
        sa.Column('num_candidates_requested', sa.Integer, nullable=False),
        sa.Column('num_candidates_generated', sa.Integer, nullable=False),
        sa.Column('safety_decisions', sa.JSON, nullable=True),
        sa.Column('warnings', sa.ARRAY(sa.String), nullable=True),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
```

### 0.3 Core Data Models

**Create `src/models/meme_models.py`:**

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# Request models
class RenderConfig(BaseModel):
    size: Literal[512, 768, 1024] = 768
    format: Literal["png", "jpg", "webp"] = "png"
    watermark: bool = False


class TemplateFilters(BaseModel):
    include_tags: Optional[list[str]] = None
    exclude_tags: Optional[list[str]] = None
    template_ids: Optional[list[str]] = None
    format: Optional[Literal["single", "two-panel", "four-panel", "caption-only"]] = None


class MemeGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    url: Optional[str] = None
    num_candidates: int = Field(default=10, ge=1, le=25)
    tone: Optional[Literal["dry", "wholesome", "savage", "absurdist", "neutral"]] = None
    audience: Optional[Literal["general", "tech", "finance", "sports"]] = None
    style: Optional[Literal["classic-impact", "modern", "minimal"]] = None
    safety_mode: Literal["strict", "standard"] = "standard"
    template_filters: Optional[TemplateFilters] = None
    render: RenderConfig = Field(default_factory=RenderConfig)
    language: str = "en"


# Response models
class MemeScores(BaseModel):
    humor: float = Field(..., ge=0.0, le=1.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    clarity: float = Field(..., ge=0.0, le=1.0)
    safety: float = Field(..., ge=0.0, le=1.0)
    originality: float = Field(..., ge=0.0, le=1.0)


class MemeCandidate(BaseModel):
    candidate_id: str
    template_id: str
    template_name: str
    captions: list[str]
    image_url: str
    alt_text: str
    explanation: str
    scores: MemeScores
    citations: Optional[list[str]] = None


class MemeGenerateResponse(BaseModel):
    trace_id: str
    candidates: list[MemeCandidate]
    warnings: Optional[list[str]] = None


# Internal models
class StoryBrief(BaseModel):
    who: Optional[str] = None
    what: str
    when: Optional[str] = None
    where: Optional[str] = None
    key_events: list[str]
    main_tension: str
    reactions: list[str] = []
    key_entities: list[str] = []
    required_assets: list[str] = []
    sentiment: str
```

### 0.4 Database Access Layer

**Create `src/db/template_repository.py`:**

```python
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Template
from loguru import logger as log


class TemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_template(self, template_id: str) -> Optional[Template]:
        result = await self.session.execute(
            select(Template).where(Template.template_id == template_id)
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        format_filter: Optional[str] = None,
        include_tags: Optional[list[str]] = None,
        exclude_tags: Optional[list[str]] = None,
        limit: int = 50
    ) -> list[Template]:
        query = select(Template)

        if format_filter:
            query = query.where(Template.format == format_filter)

        if include_tags:
            query = query.where(Template.tags.overlap(include_tags))

        if exclude_tags:
            query = query.where(~Template.tags.overlap(exclude_tags))

        query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_template(self, template: Template) -> Template:
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template
```

### 0.5 API Routes

**Create `src/api/v1/meme_routes.py`:**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.meme_models import MemeGenerateRequest, MemeGenerateResponse
from src.services.meme_orchestrator import MemeOrchestrator
from src.db.session import get_db_session
from loguru import logger as log
import uuid

router = APIRouter(prefix="/v1/memes", tags=["memes"])


@router.post("/generate", response_model=MemeGenerateResponse)
async def generate_memes(
    request: MemeGenerateRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Generate N meme candidates from prompt and optional URL."""
    trace_id = f"tr_{uuid.uuid4().hex[:16]}"

    log.info(f"[{trace_id}] Generating memes",
             num_candidates=request.num_candidates,
             has_url=request.url is not None)

    try:
        orchestrator = MemeOrchestrator(db=db, trace_id=trace_id)
        response = await orchestrator.generate(request)
        return response
    except Exception as e:
        log.error(f"[{trace_id}] Generation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{candidate_id}")
async def get_meme_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieve metadata for a specific meme candidate."""
    # TODO: Implement candidate retrieval
    pass
```

### 0.6 Core Service: Meme Orchestrator

**Create `src/services/meme_orchestrator.py`:**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.meme_models import (
    MemeGenerateRequest,
    MemeGenerateResponse,
    MemeCandidate
)
from src.services.context_builder import ContextBuilder
from src.services.template_selector import TemplateSelector
from src.services.meme_generator import MemeGenerator
from src.services.meme_scorer import MemeScorer
from loguru import logger as log
from common import global_config


class MemeOrchestrator:
    """Orchestrates the end-to-end meme generation pipeline."""

    def __init__(self, db: AsyncSession, trace_id: str):
        self.db = db
        self.trace_id = trace_id
        self.context_builder = ContextBuilder()
        self.template_selector = TemplateSelector(db)
        self.meme_generator = MemeGenerator()
        self.scorer = MemeScorer()

    async def generate(self, request: MemeGenerateRequest) -> MemeGenerateResponse:
        """Main generation pipeline."""

        # Step 1: Build context (story brief or prompt brief)
        log.info(f"[{self.trace_id}] Building context")
        context = await self.context_builder.build(
            prompt=request.prompt,
            url=request.url
        )

        # Step 2: Select candidate templates
        log.info(f"[{self.trace_id}] Selecting templates")
        templates = await self.template_selector.select(
            context=context,
            filters=request.template_filters,
            tone=request.tone,
            num_candidates=request.num_candidates
        )

        # Step 3: Generate meme candidates (parallel)
        log.info(f"[{self.trace_id}] Generating {len(templates)} candidates")
        candidates = await self.meme_generator.generate_batch(
            context=context,
            templates=templates,
            request=request,
            trace_id=self.trace_id
        )

        # Step 4: Score and rank candidates
        log.info(f"[{self.trace_id}] Scoring candidates")
        scored_candidates = await self.scorer.score_and_rank(
            candidates=candidates,
            request=request
        )

        return MemeGenerateResponse(
            trace_id=self.trace_id,
            candidates=scored_candidates,
            warnings=None
        )
```

### 0.7 Context Builder Service (Phase 0: Prompt-only)

**Create `src/services/context_builder.py`:**

```python
from typing import Optional
from src.models.meme_models import StoryBrief
from utils.llm.dspy_inference import DSPYInference
import dspy
from loguru import logger as log


class ContextBuilderSignature(dspy.Signature):
    """Extract structured context from a meme prompt."""
    prompt: str = dspy.InputField(desc="User's meme generation prompt")
    url: Optional[str] = dspy.InputField(desc="Optional URL for context", default=None)

    story_brief: str = dspy.OutputField(desc="Structured story brief as JSON")


class ContextBuilder:
    """Builds story brief from prompt (and URL in later phases)."""

    def __init__(self):
        self.inference = DSPYInference(
            pred_signature=ContextBuilderSignature,
            observe=True
        )

    async def build(self, prompt: str, url: Optional[str] = None) -> StoryBrief:
        """
        Phase 0: Extracts context from prompt only.
        Phase 1+: Will add URL fetching and web search.
        """

        if url:
            log.warning("URL provided but URL context building not yet implemented")

        # Generate story brief
        result = await self.inference.run(
            prompt=prompt,
            url=url
        )

        # Parse and return
        import json
        brief_data = json.loads(result.story_brief)
        return StoryBrief(**brief_data)
```

### 0.8 Template Selection Service

**Create `src/services/template_selector.py`:**

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.template_repository import TemplateRepository
from src.models.meme_models import StoryBrief, TemplateFilters
from src.db.models import Template
from loguru import logger as log


class TemplateSelector:
    """Selects best-fit templates based on context and filters."""

    def __init__(self, db: AsyncSession):
        self.repo = TemplateRepository(db)

    async def select(
        self,
        context: StoryBrief,
        filters: Optional[TemplateFilters],
        tone: Optional[str],
        num_candidates: int
    ) -> list[Template]:
        """
        Phase 0: Basic filtering by tags/format.
        Phase 2+: Semantic search using embeddings.
        """

        # Apply filters
        include_tags = filters.include_tags if filters else None
        exclude_tags = filters.exclude_tags if filters else None
        format_filter = filters.format if filters else None

        # Get candidate templates
        templates = await self.repo.list_templates(
            format_filter=format_filter,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            limit=num_candidates * 2  # Over-fetch for diversity
        )

        # Phase 0: Simple random selection
        # Phase 2+: Re-rank by semantic similarity and tone affinity
        import random
        selected = random.sample(templates, min(num_candidates, len(templates)))

        log.info(f"Selected {len(selected)} templates from {len(templates)} candidates")
        return selected
```

### 0.9 Meme Generation Service

**Create `src/services/meme_generator.py`:**

```python
import asyncio
import uuid
from src.models.meme_models import StoryBrief, MemeGenerateRequest, MemeCandidate, MemeScores
from src.db.models import Template
from src.services.image_storage import ImageStorage
from common import global_config
from loguru import logger as log


class MemeGenerator:
    """Generates meme images using Google Nano Banana Pro."""

    def __init__(self):
        self.storage = ImageStorage()
        self.api_key = global_config.GOOGLE_NANO_BANANA_API_KEY

    async def generate_batch(
        self,
        context: StoryBrief,
        templates: list[Template],
        request: MemeGenerateRequest,
        trace_id: str
    ) -> list[MemeCandidate]:
        """Generate meme candidates in parallel."""

        tasks = [
            self._generate_single(context, template, request, trace_id)
            for template in templates
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        candidates = [r for r in results if not isinstance(r, Exception)]

        log.info(f"[{trace_id}] Generated {len(candidates)}/{len(templates)} candidates")
        return candidates

    async def _generate_single(
        self,
        context: StoryBrief,
        template: Template,
        request: MemeGenerateRequest,
        trace_id: str
    ) -> MemeCandidate:
        """Generate a single meme candidate."""

        # Build generation prompt
        prompt = self._build_generation_prompt(context, template, request)

        # Call Nano Banana Pro API
        image_data = await self._call_nano_banana(prompt)

        # Upload to storage
        candidate_id = f"m_{uuid.uuid4().hex[:16]}"
        image_url = await self.storage.upload(
            image_data=image_data,
            candidate_id=candidate_id,
            format=request.render.format
        )

        # TODO: Extract captions from image or metadata
        captions = []

        # Generate alt text
        alt_text = f"Meme using {template.name} template"

        # Generate explanation
        explanation = f"Selected {template.name} for its {template.format} format"

        # Placeholder scores (will be filled by scorer)
        scores = MemeScores(
            humor=0.5,
            relevance=0.5,
            clarity=0.5,
            safety=0.5,
            originality=0.5
        )

        return MemeCandidate(
            candidate_id=candidate_id,
            template_id=template.template_id,
            template_name=template.name,
            captions=captions,
            image_url=image_url,
            alt_text=alt_text,
            explanation=explanation,
            scores=scores,
            citations=None
        )

    def _build_generation_prompt(
        self,
        context: StoryBrief,
        template: Template,
        request: MemeGenerateRequest
    ) -> str:
        """Build the prompt for image generation."""

        prompt = f"""Generate a meme image based on:

Context: {context.what}
Tension: {context.main_tension}
Template: {template.name} ({template.format})

Requirements:
- Tone: {request.tone or 'neutral'}
- Audience: {request.audience or 'general'}
- Safety: {request.safety_mode}
"""
        return prompt

    async def _call_nano_banana(self, prompt: str) -> bytes:
        """Call Google Nano Banana Pro API."""
        # TODO: Implement actual API call
        # For now, return placeholder
        log.warning("Nano Banana API not yet implemented")
        return b""
```

### 0.10 Scoring Service

**Create `src/services/meme_scorer.py`:**

```python
from src.models.meme_models import MemeCandidate, MemeGenerateRequest, MemeScores
from utils.llm.dspy_inference import DSPYInference
import dspy
from common import global_config
from loguru import logger as log


class ScoringSignature(dspy.Signature):
    """Score a meme candidate on multiple dimensions."""
    context: str = dspy.InputField()
    template_name: str = dspy.InputField()
    explanation: str = dspy.InputField()
    dimension: str = dspy.InputField(desc="humor, relevance, clarity, safety, or originality")

    score: float = dspy.OutputField(desc="Score from 0.0 to 1.0")
    reasoning: str = dspy.OutputField()


class MemeScorer:
    """Scores and ranks meme candidates."""

    def __init__(self):
        self.inference = DSPYInference(
            pred_signature=ScoringSignature,
            observe=True
        )

    async def score_and_rank(
        self,
        candidates: list[MemeCandidate],
        request: MemeGenerateRequest
    ) -> list[MemeCandidate]:
        """Score all candidates and return ranked list."""

        # Score each candidate on all dimensions
        for candidate in candidates:
            scores = await self._score_candidate(candidate)
            candidate.scores = scores

        # Rank by weighted score
        ranked = self._rank_candidates(candidates, request)

        return ranked

    async def _score_candidate(self, candidate: MemeCandidate) -> MemeScores:
        """Score a single candidate on all dimensions."""

        dimensions = ["humor", "relevance", "clarity", "safety", "originality"]
        scores = {}

        for dim in dimensions:
            result = await self.inference.run(
                context=candidate.explanation,
                template_name=candidate.template_name,
                explanation=candidate.explanation,
                dimension=dim
            )
            scores[dim] = float(result.score)

        return MemeScores(**scores)

    def _rank_candidates(
        self,
        candidates: list[MemeCandidate],
        request: MemeGenerateRequest
    ) -> list[MemeCandidate]:
        """Rank candidates by weighted score."""

        weights = global_config.meme_generator.ranking.weights

        def compute_score(candidate: MemeCandidate) -> float:
            s = candidate.scores
            return (
                weights.relevance * s.relevance +
                weights.humor * s.humor +
                weights.clarity * s.clarity +
                weights.originality * s.originality +
                weights.safety * s.safety
            )

        ranked = sorted(candidates, key=compute_score, reverse=True)
        return ranked
```

### 0.11 Image Storage Service

**Create `src/services/image_storage.py`:**

```python
import boto3
from botocore.exceptions import ClientError
from common import global_config
from loguru import logger as log


class ImageStorage:
    """Handles image upload and signed URL generation."""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=global_config.object_storage.region
        )
        self.bucket = global_config.object_storage.bucket

    async def upload(
        self,
        image_data: bytes,
        candidate_id: str,
        format: str
    ) -> str:
        """Upload image to S3 and return signed URL."""

        key = f"memes/{candidate_id}.{format}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=image_data,
                ContentType=f"image/{format}"
            )

            # Generate signed URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=global_config.object_storage.signed_url_expiry
            )

            return url

        except ClientError as e:
            log.error(f"S3 upload failed for {candidate_id}", error=str(e))
            raise
```

---

## Phase 1: URL Context & Web Search

### Goal
Add URL ingestion and web search to build richer story briefs.

### 1.1 Enhanced Context Builder

**Update `src/services/context_builder.py`:**

```python
class WebSearchContextSignature(dspy.Signature):
    """Build story brief using web search (via OpenAI with search enabled)."""
    prompt: str = dspy.InputField()
    url: str = dspy.InputField()

    story_brief: str = dspy.OutputField(desc="Structured JSON story brief")
    citations: list[str] = dspy.OutputField(desc="List of source URLs used")


class ContextBuilder:
    def __init__(self):
        # Use OpenAI with web search for URL contexts
        self.web_inference = DSPYInference(
            pred_signature=WebSearchContextSignature,
            observe=True,
            model="openai/gpt-4-turbo-preview"  # With web search enabled
        )

        # Existing prompt-only inference
        self.prompt_inference = DSPYInference(
            pred_signature=ContextBuilderSignature,
            observe=True
        )

    async def build(self, prompt: str, url: Optional[str] = None) -> tuple[StoryBrief, list[str]]:
        """Build context with optional URL and web search."""

        if url:
            # Use web search
            result = await self.web_inference.run(prompt=prompt, url=url)
            brief_data = json.loads(result.story_brief)
            return StoryBrief(**brief_data), result.citations
        else:
            # Prompt-only
            result = await self.prompt_inference.run(prompt=prompt)
            brief_data = json.loads(result.story_brief)
            return StoryBrief(**brief_data), []
```

### 1.2 Logo Resolution Service

**Create `src/services/logo_service.py`:**

```python
import aiohttp
from common import global_config
from loguru import logger as log


class LogoService:
    """Fetches brand logos on-demand via logo.dev."""

    def __init__(self):
        self.base_url = global_config.logo_service.base_url
        self.api_key = global_config.LOGO_DEV_API_KEY

    async def fetch_logo(self, company: str) -> Optional[str]:
        """Fetch logo URL for a company. Returns None if not found."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/search",
                    params={"q": company},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("logo_url")
                    else:
                        log.warning(f"Logo fetch failed for {company}", status=resp.status)
                        return None
        except Exception as e:
            log.error(f"Logo fetch error for {company}", error=str(e))
            return None
```

### 1.3 Update Meme Generator for Asset Resolution

**Update `src/services/meme_generator.py`:**

```python
from src.services.logo_service import LogoService

class MemeGenerator:
    def __init__(self):
        self.storage = ImageStorage()
        self.logo_service = LogoService()
        self.api_key = global_config.GOOGLE_NANO_BANANA_API_KEY

    async def _generate_single(
        self,
        context: StoryBrief,
        template: Template,
        request: MemeGenerateRequest,
        trace_id: str
    ) -> MemeCandidate:
        """Generate with logo resolution if needed."""

        # Resolve logos if template requires them
        logos = {}
        if template.external_assets and context.required_assets:
            for asset in context.required_assets:
                logo_url = await self.logo_service.fetch_logo(asset)
                if logo_url:
                    logos[asset] = logo_url

        # Build generation prompt with logos
        prompt = self._build_generation_prompt(context, template, request, logos)

        # ... rest of generation
```

---

## Phase 2: Template Embeddings & Semantic Search

### Goal
Implement vector embeddings for templates and semantic search.

### 2.1 Embedding Generation

**Create `src/services/embedding_service.py`:**

```python
from openai import AsyncOpenAI
from common import global_config


class EmbeddingService:
    """Generate embeddings for templates and queries."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=global_config.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    async def embed_template(self, template: Template) -> list[float]:
        """Generate embedding for template metadata."""

        text_parts = [
            template.name,
            " ".join(template.tags or []),
            " ".join(template.tone_affinity or [])
        ]

        if template.example_captions:
            text_parts.extend([str(ex) for ex in template.example_captions])

        text = " ".join(text_parts)
        return await self.embed_text(text)
```

### 2.2 Alembic Migration for pgvector

**Create migration for vector extension:**

```python
# alembic/versions/002_add_pgvector.py

def upgrade():
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Change embedding column to vector type
    op.execute("ALTER TABLE templates ALTER COLUMN embedding TYPE vector(1536)")

    # Add vector similarity index
    op.execute("CREATE INDEX idx_templates_embedding ON templates USING ivfflat (embedding vector_cosine_ops)")
```

### 2.3 Enhanced Template Selector with Semantic Search

**Update `src/services/template_selector.py`:**

```python
from src.services.embedding_service import EmbeddingService
from sqlalchemy import text

class TemplateSelector:
    def __init__(self, db: AsyncSession):
        self.repo = TemplateRepository(db)
        self.embedding_service = EmbeddingService()

    async def select(
        self,
        context: StoryBrief,
        filters: Optional[TemplateFilters],
        tone: Optional[str],
        num_candidates: int
    ) -> list[Template]:
        """Select templates using semantic search."""

        # Build query text from context
        query_text = f"{context.what} {context.main_tension}"
        query_embedding = await self.embedding_service.embed_text(query_text)

        # Semantic search using pgvector
        query = text("""
            SELECT template_id, name, format, tags, tone_affinity,
                   (embedding <=> :query_embedding) as distance
            FROM templates
            WHERE 1=1
        """)

        # Apply filters
        if filters and filters.format:
            query = text(str(query) + " AND format = :format")

        query = text(str(query) + " ORDER BY distance LIMIT :limit")

        result = await self.repo.session.execute(
            query,
            {
                "query_embedding": query_embedding,
                "format": filters.format if filters else None,
                "limit": num_candidates * 2
            }
        )

        template_ids = [row.template_id for row in result]

        # Load full templates
        templates = []
        for tid in template_ids:
            t = await self.repo.get_template(tid)
            if t:
                templates.append(t)

        # Re-rank by tone affinity
        if tone:
            templates = self._rerank_by_tone(templates, tone)

        # Ensure diversity (no duplicates)
        return templates[:num_candidates]

    def _rerank_by_tone(self, templates: list[Template], tone: str) -> list[Template]:
        """Re-rank by tone affinity."""
        def tone_score(t: Template) -> float:
            if t.tone_affinity and tone in t.tone_affinity:
                return 1.0
            return 0.0

        return sorted(templates, key=tone_score, reverse=True)
```

---

## Phase 3: Safety Tuning & Sensitive Topics

### Goal
Implement robust safety checks and sensitive topic handling.

### 3.1 Safety Analyzer Service

**Create `src/services/safety_analyzer.py`:**

```python
from utils.llm.dspy_inference import DSPYInference
import dspy
from loguru import logger as log


class SafetyCheckSignature(dspy.Signature):
    """Analyze content for safety concerns."""
    prompt: str = dspy.InputField()
    url_context: Optional[str] = dspy.InputField(default=None)

    is_safe: bool = dspy.OutputField()
    concern_categories: list[str] = dspy.OutputField()
    reasoning: str = dspy.OutputField()
    safe_alternative: Optional[str] = dspy.OutputField()


class SafetyAnalyzer:
    """Analyzes requests and candidates for safety violations."""

    BLOCKED_CATEGORIES = [
        "hate_speech",
        "targeted_harassment",
        "csam",
        "self_harm",
        "doxxing",
        "graphic_violence"
    ]

    def __init__(self):
        self.inference = DSPYInference(
            pred_signature=SafetyCheckSignature,
            observe=True
        )

    async def check_request(
        self,
        prompt: str,
        url_context: Optional[str] = None,
        safety_mode: str = "standard"
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if request is safe.
        Returns: (is_safe, blocked_reason, safe_alternative)
        """

        result = await self.inference.run(
            prompt=prompt,
            url_context=url_context
        )

        if not result.is_safe:
            blocked_categories = [
                c for c in result.concern_categories
                if c in self.BLOCKED_CATEGORIES
            ]

            if blocked_categories:
                reason = f"Content violates policy: {', '.join(blocked_categories)}"
                return False, reason, result.safe_alternative

        return True, None, None

    async def downgrade_templates_for_tragedy(
        self,
        templates: list[Template],
        context: StoryBrief
    ) -> list[Template]:
        """Filter out edgy templates for tragedy/violence topics."""

        # Check if context involves tragedy
        tragedy_keywords = ["death", "shooting", "attack", "tragedy", "disaster"]
        is_tragedy = any(kw in context.what.lower() for kw in tragedy_keywords)

        if is_tragedy:
            # Filter out templates with edgy tags
            edgy_tags = ["savage", "dark", "edgy", "controversial"]
            filtered = [
                t for t in templates
                if not any(tag in (t.tags or []) for tag in edgy_tags)
            ]
            log.info(f"Filtered {len(templates) - len(filtered)} edgy templates for tragedy topic")
            return filtered

        return templates
```

### 3.2 Update Orchestrator with Safety Checks

**Update `src/services/meme_orchestrator.py`:**

```python
from src.services.safety_analyzer import SafetyAnalyzer

class MemeOrchestrator:
    def __init__(self, db: AsyncSession, trace_id: str):
        # ... existing services
        self.safety_analyzer = SafetyAnalyzer()

    async def generate(self, request: MemeGenerateRequest) -> MemeGenerateResponse:
        """Pipeline with safety checks."""

        # Pre-generation safety check
        is_safe, blocked_reason, safe_alt = await self.safety_analyzer.check_request(
            prompt=request.prompt,
            url_context=request.url,
            safety_mode=request.safety_mode
        )

        if not is_safe:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "unsafe_content",
                    "reason": blocked_reason,
                    "safe_alternative": safe_alt
                }
            )

        # Build context
        context = await self.context_builder.build(
            prompt=request.prompt,
            url=request.url
        )

        # Select templates
        templates = await self.template_selector.select(
            context=context,
            filters=request.template_filters,
            tone=request.tone,
            num_candidates=request.num_candidates
        )

        # Downgrade templates if tragedy/violence
        templates = await self.safety_analyzer.downgrade_templates_for_tragedy(
            templates, context
        )

        # ... rest of pipeline
```

---

## Phase 4: Template Management & Admin Features

### Goal
Enable template CRUD operations and admin tools.

### 4.1 Template Admin Routes

**Create `src/api/v1/template_routes.py`:**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.template_repository import TemplateRepository
from src.db.models import Template
from src.services.embedding_service import EmbeddingService
from src.db.session import get_db_session

router = APIRouter(prefix="/v1/templates", tags=["templates"])


@router.get("")
async def list_templates(
    format: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session)
):
    """List templates with optional filters."""
    repo = TemplateRepository(db)

    include_tags = tags.split(",") if tags else None

    templates = await repo.list_templates(
        format_filter=format,
        include_tags=include_tags,
        limit=limit
    )

    return {"templates": templates}


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get template details."""
    repo = TemplateRepository(db)
    template = await repo.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.post("")
async def create_template(
    template: Template,
    db: AsyncSession = Depends(get_db_session)
):
    """Create new template with embedding generation."""
    repo = TemplateRepository(db)
    embedding_service = EmbeddingService()

    # Generate embedding
    template.embedding = await embedding_service.embed_template(template)

    created = await repo.create_template(template)
    return created
```

---

## Testing Strategy

### Phase 0 Tests

**Create `tests/test_meme_orchestrator.py`:**

```python
from tests.test_template import TestTemplate
from src.services.meme_orchestrator import MemeOrchestrator
from src.models.meme_models import MemeGenerateRequest
import pytest


class TestMemeOrchestrator(TestTemplate):
    @pytest.mark.asyncio
    async def test_prompt_only_generation(self, db_session):
        """Test basic prompt-only meme generation."""
        orchestrator = MemeOrchestrator(db=db_session, trace_id="test_trace")

        request = MemeGenerateRequest(
            prompt="Make a meme about coffee addiction",
            num_candidates=3
        )

        response = await orchestrator.generate(request)

        assert response.trace_id == "test_trace"
        assert len(response.candidates) <= 3
        assert all(c.template_id for c in response.candidates)
```

**Create `tests/test_template_selector.py`:**

```python
from tests.test_template import TestTemplate
from src.services.template_selector import TemplateSelector
from src.models.meme_models import StoryBrief
import pytest


class TestTemplateSelector(TestTemplate):
    @pytest.mark.asyncio
    async def test_basic_selection(self, db_session):
        """Test template selection with filters."""
        selector = TemplateSelector(db=db_session)

        context = StoryBrief(
            what="Tech startup fails",
            main_tension="overhyped vs reality",
            key_events=[],
            sentiment="negative"
        )

        templates = await selector.select(
            context=context,
            filters=None,
            tone="dry",
            num_candidates=5
        )

        assert len(templates) <= 5
```

---

## Deployment Checklist

### Environment Setup
- [ ] Create `.env` with all API keys
- [ ] Set up Postgres with pgvector extension
- [ ] Set up S3 bucket for image storage
- [ ] Configure LangFuse for observability

### Database
- [ ] Run `alembic upgrade head`
- [ ] Seed initial templates (Phase 0: 10-20 templates)
- [ ] Generate embeddings for all templates (Phase 2+)

### Dependencies
- [ ] Run `make setup`
- [ ] Install Google Nano Banana SDK
- [ ] Install pgvector drivers

### Configuration
- [ ] Update `global_config.yaml` with all settings
- [ ] Set ranking weights
- [ ] Configure safety mode defaults
- [ ] Set performance targets and timeouts

### Testing
- [ ] Run `make test`
- [ ] Run `make ci` (ruff, vulture, ty)
- [ ] Load test with 10 concurrent requests

### Monitoring
- [ ] Set up LangFuse traces
- [ ] Configure latency alerts (P95 > 20s)
- [ ] Track safety refusal rate
- [ ] Monitor template coverage

---

## Implementation Order Summary

1. **Phase 0** (Weeks 1-2)
   - Database schema + migrations
   - Core API routes
   - Prompt-only context builder
   - Basic template selection (random)
   - Meme generation via Nano Banana
   - LLM-based scoring
   - Image storage

2. **Phase 1** (Week 3)
   - URL context + web search
   - Logo resolution service
   - Citation tracking

3. **Phase 2** (Week 4)
   - Template embeddings
   - pgvector setup
   - Semantic search
   - Tone-based re-ranking

4. **Phase 3** (Week 5)
   - Safety analyzer
   - Sensitive topic detection
   - Template downgrading for tragedies

5. **Phase 4** (Week 6)
   - Template CRUD API
   - Admin features
   - Custom template uploads

---

## Open Questions & Decisions Needed

1. **Google Nano Banana Pro API**: Is this a real API? Need actual endpoint details.
2. **Template seed data**: Where do we get the initial 10-20 templates?
3. **Watermark design**: What should the watermark look like?
4. **Rate limiting**: Should we add rate limiting at the API gateway level?
5. **Cost tracking**: Should we track per-request costs (LLM calls + storage)?
6. **Authentication**: How do we handle API key authentication?

---

## Next Steps

1. Review this plan with the team
2. Make decisions on open questions
3. Set up development environment
4. Begin Phase 0 implementation
5. Create initial template seed data
