# Implementation Plan: Context-Aware Meme Generator API

## Overview

This plan outlines the implementation of the Context-Aware Meme Generator API based on the PRD. The implementation follows a phased approach, starting with core functionality and progressively adding complexity.

## Phase 0: Foundation & Prompt-Only Generation

### Goal
Establish basic API infrastructure and generate memes from text prompts without URL context.

### Project Structure
```
src/
├── api/
│   ├── routes/
│   │   └── meme/
│   │       ├── __init__.py
│   │       └── generate.py
│   ├── auth/
│   │   └── unified_auth.py
│   └── limits.py
├── db/
│   ├── models/
│   │   └── public/
│   │       └── templates.py
│   └── utils/
│       └── template_repository.py
├── services/
│   └── meme/
│       ├── __init__.py
│       ├── orchestrator.py
│       ├── context/
│       │   ├── __init__.py
│       │   ├── builder.py
│       │   └── models.py
│       ├── templates/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   ├── selector.py
│       │   └── models.py
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── caption_generator.py
│       │   └── image_renderer.py
│       ├── scoring/
│       │   ├── __init__.py
│       │   └── scorer.py
│       ├── safety/
│       │   ├── __init__.py
│       │   └── analyzer.py
│       └── storage/
│           ├── __init__.py
│           └── image_storage.py
└── utils/

data/
├── templates/
│   ├── template_001.jpg
│   ├── template_002.jpg
│   └── ...
├── outputs/
└── templates.json
```

### 0.0 Template Annotation & Initial Dataset

**Goal**: Create initial template dataset with rich metadata before building the system.

**Steps**:
1. Ask Eito to provide 5-10 meme template images
2. Save images locally in `data/templates/` as `template_001.jpg`, `template_002.jpg`, etc.
3. For each template, manually annotate:
   - `template_id`: Unique identifier
   - `name`: Template name (e.g., "Drake Hotline Bling", "Distracted Boyfriend")
   - `format`: "single", "two-panel", "four-panel", etc.
   - `text_areas`: Number and description of text areas (e.g., "top text, bottom text" or "panel 1, panel 2")
   - `aspect_ratio`: Preferred aspect ratio (e.g., "1:1", "4:3", "16:9")
   - `tags`: Array of relevant tags (e.g., ["reaction", "comparison", "tech"])
   - `tone_affinity`: Array of tones (e.g., ["dry", "savage", "wholesome"])
   - `example_captions`: Array of example caption sets
4. Store metadata in `data/templates.json`:
```json
{
  "templates": [
    {
      "template_id": "template_001",
      "name": "Drake Hotline Bling",
      "format": "two-panel",
      "image_path": "data/templates/template_001.jpg",
      "text_areas": "Two panels: top text for rejection, bottom text for approval",
      "aspect_ratio": "1:1",
      "tags": ["reaction", "comparison", "choice"],
      "tone_affinity": ["dry", "savage"],
      "example_captions": [
        ["Old way of doing things", "New better way"],
        ["Bug in production", "Ignoring it until Monday"]
      ]
    }
  ]
}
```

**Note**: Phase 0 uses local files + JSON for rapid iteration. Migration to Postgres + pgvector happens in Phase 1.5 after core functionality is validated.

### 0.1 Project Setup & Configuration

**Note**: Add corresponding Pydantic models to `common/config_models.py` for type validation (MemeGeneratorConfig, GeminiConfig with embedding_dimension as Literal[768, 1536, 3072])

**Config additions to `global_config.yaml`:**
```yaml
meme_generator:
  default_num_candidates: 4
  max_candidates: 25
  default_timeout: 30  # Increased for nano banana pro thinking mode
  default_resolution: "1K"  # Options: "1K", "2K", "4K"
  default_render_format: "png"

  # Performance targets
  prompt_only_p50_target: 10  # Slightly increased for nano banana pro
  url_based_p50_target: 18

  # Cost controls
  max_web_sources: 5
  max_templates_per_request: 50
  max_reference_images: 14  # Nano banana pro supports up to 14 reference images (6 objects + 5 humans + logos)
  # Note: Image file size limits should be verified during implementation against actual Gemini API constraints

  # Embedding configuration
  embedding_dimension: 768  # CRITICAL: Changing this requires regenerating all embeddings and DB migration
  # Options: 768 (balanced), 1536 (higher quality), 3072 (full Gemini default)
  # Tradeoff: Lower dims = faster search, less storage; Higher dims = better quality, slower search

llm_providers:
  gemini:
    default_model: "gemini/gemini-3-flash-preview"
    image_generation_model: "gemini-3-pro-image-preview"  # Nano banana pro for meme generation (high-quality text rendering, up to 14 reference images)
    enable_web_search: true  # Uses Gemini's native grounding with Google Search (billing applies per grounded query)
    embedding_model: "gemini-embedding-001"  # For template semantic search

logo_service:
  image_base_url: "https://img.logo.dev"  # Image CDN endpoint (uses publishable key pk_* via ?token= query param)
  api_base_url: "https://api.logo.dev"     # API endpoint for search/metadata (uses secret key sk_* via Authorization header)
  cache_ttl: 3600
  # Note: Free tier requires visible attribution link to logo.dev
  # Two key types: publishable (pk_*) for client-side images, secret (sk_*) for server-side API calls

object_storage:
  provider: "railway"  # Uses Railway Buckets (S3-compatible, private only)
  bucket: "memegen-outputs"
  signed_url_expiry: 3600  # Seconds (Railway supports up to 90 days max)

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
GEMINI_API_KEY=...
LOGO_DEV_PUBLISHABLE_KEY=pk_...  # For client-side image CDN requests (img.logo.dev)
LOGO_DEV_SECRET_KEY=sk_...       # For server-side API calls (api.logo.dev - search/metadata)
```

**Dependencies to add:**
```bash
uv add google-genai  # Gemini 3 Pro Image (nano banana pro) for high-quality meme image generation
uv add numpy         # In-memory cosine similarity (Phase 1), ARM macOS optimized with Accelerate
```

### 0.2 Core Data Models

**Create `src/api/routes/meme/generate.py` with Pydantic models:**
- `MemeGenerateRequest`: Prompt, URL, num_candidates, tone, audience, style, safety_mode, template_filters, render config
- `MemeGenerateResponse`: trace_id, candidates list, warnings
- `MemeCandidate`: candidate_id, template info, captions, image_url, scores, citations
- `MemeScores`: humor, relevance, clarity, safety, originality (0.0-1.0)

**Create `src/services/meme/context/models.py` for internal models:**
- `StoryBrief`: Context extraction model (who/what/when/where, key_events, main_tension, sentiment, required_assets)

**Create `src/services/meme/templates/models.py`:**
- `Template`: Template dataclass loaded from JSON (Phase 0) or DB (Phase 1.5+)

### 0.3 Template Loader (Phase 0: JSON-based)

**Create `src/services/meme/templates/loader.py`:**
- Loads templates from `data/templates.json`
- Methods: `get_template()`, `list_templates()`, `filter_by_tags()`
- Simple in-memory filtering by format, tags (include/exclude)

**Note**: Phase 1.5 will migrate to `src/db/utils/template_repository.py` with Postgres + pgvector

### 0.4 API Routes

**Create `src/api/routes/meme/generate.py`:**
- Define Pydantic models: `MemeGenerateRequest`, `MemeGenerateResponse`, `MemeCandidate`, etc.
- `POST /v1/memes/generate`: Main endpoint
  - Uses `get_authenticated_user(request, db)` from `unified_auth` (returns AuthenticatedUser with id and email)
  - Uses `ensure_daily_limit(db, user_uuid, limit_name, enforce)` from `limits` (takes uuid.UUID, not string)
- `GET /v1/memes/{candidate_id}`: Retrieve specific meme metadata (Phase 1.5+)
- Register in `src/api/routes/__init__.py` following existing pattern

### 0.5 Core Service: Meme Orchestrator

**Create `src/services/meme/orchestrator.py`:**

Pipeline:
1. Build context using `ContextBuilder` (extracts StoryBrief from prompt using gemini-3-flash-preview)
2. Select templates using `TemplateSelector` (filters by tags, format, tone)
3. Generate captions using LLM (gemini-3-flash-preview based on context and template)
4. Generate meme images using nano banana pro (Gemini 3 Pro Image) with template + captions + optional logos
5. Score and rank candidates using `MemeScorer` (LLM-based scoring on 5 dimensions)

### 0.6 Context Builder Service (Phase 0: Prompt-only)

**Create `src/services/meme/context/builder.py`:**
- Uses DSPYInference with gemini/gemini-3-flash-preview (LLM for text understanding)
- Extracts structured StoryBrief from prompt (who, what, tension, sentiment, required_assets)
- Decorated with `@observe()` for LangFuse tracing (note the parentheses)
- Phase 0: Prompt-only, Phase 2+: Will add URL fetching and web search

### 0.7 Template Selection Service

**Create `src/services/meme/templates/selector.py`:**
- Phase 0: Loads from JSON via `TemplateLoader`, basic filtering by tags/format, random selection
- Phase 3+: Semantic search using pgvector embeddings and tone affinity re-ranking

### 0.8 Meme Generation Services

**Create `src/services/meme/generation/caption_generator.py`:**
- Uses DSPYInference with gemini/gemini-3-flash-preview (LLM) to generate witty captions
- Takes context (StoryBrief), template metadata, tone/audience as input
- Decorated with `@observe()` for LangFuse tracing (note the parentheses)
- Returns list of caption texts matching the template format (e.g., ["top text", "bottom text"] for two-panel)

**Create `src/services/meme/generation/meme_generator.py`:**
- Uses Gemini 3 Pro Image (nano banana pro) API for image generation
- Takes template image, captions, and optional logo images as input
- Constructs multimodal prompt with:
  - Template image (as base64 or file path)
  - Caption text in natural language (e.g., "Add 'TOP TEXT' at top and 'BOTTOM TEXT' at bottom in bold white Impact font with black stroke, meme style")
  - Optional brand logos (up to 14 reference images supported)
- Decorated with `@observe()` for LangFuse tracing (note the parentheses)
- Returns generated meme image (saves to `data/outputs/` in Phase 0, uploads to Railway in Phase 1.5+)
- Model: `gemini-3-pro-image-preview` (supports 1K/2K/4K resolutions, improved text rendering)
- Config: Supports aspect ratio control via `image_config.aspect_ratio` (1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)
- Features: "Thinking" mode for better composition, grounding with Google Search

**Benefits of using nano banana pro over manual text overlay:**
- No need to manage fonts, text wrapping, positioning, stroke effects manually
- **Superior text rendering quality** - significantly improved legible, stylized text
- Can handle complex layouts and multi-panel templates naturally
- Supports up to **14 reference images** (6 for objects + 5 for humans + additional logos)
- **"Thinking" mode** - internal reasoning for better composition before final output
- **Higher resolution options** - 1K, 2K, 4K (default 1K)
- **More aspect ratios** - 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
- Optional grounding with Google Search for real-world context
- Simplifies codebase by removing PIL/Pillow dependencies and custom rendering logic
- SynthID watermark automatically included

### 0.9 Scoring Service

**Create `src/services/meme/scoring/scorer.py`:**
- Uses DSPYInference with gemini/gemini-3-flash-preview (LLM) to score candidates on 5 dimensions
- Decorated with `@observe()` for LangFuse tracing (note the parentheses)
- Ranks by weighted sum (configurable in `global_config.yaml`)
- Returns sorted list of candidates

### 0.10 Image Storage Service

**Create `src/services/meme/storage/image_storage.py`:**
- Phase 0: Save to `data/outputs/` directory, return file paths
- Phase 1.5+: Upload to Railway Buckets (S3-compatible), return presigned URLs with configurable expiry
  - Note: Railway Buckets are private by default; use presigned URLs for temporary access
  - Max expiry: 90 days (config defaults to 3600s/1 hour)
- Handles error cases and logging

---

## Phase 1: Embeddings & Semantic Search (JSON-based)

### Goal
Add vector embeddings and semantic template selection while still using JSON for rapid iteration.

### 1.1 Embedding Generation (JSON-based)
**Create `src/services/meme/templates/embedding_service.py`:**
- Use Gemini embeddings API (model from `global_config.llm_providers.gemini.embedding_model`)
- Generate embeddings from template metadata (name, tags, tone_affinity, example_captions)
- **Embedding dimension**: Read from `global_config.meme_generator.embedding_dimension` (default: 768)
  - Pass to Gemini API via `output_dimensionality` parameter
  - Note: Gemini supports 768, 1536, 3072 dimensions
  - Tradeoff: Lower dims = faster search, less storage; Higher dims = better quality
  - **CRITICAL**: Once set and deployed, changing dimension requires:
    1. Regenerating all embeddings (cost + time)
    2. Alembic migration to alter vector column type
    3. Downtime or dual-write strategy during migration
- Store embeddings in `data/templates.json` as arrays
- Add embedding generation script: `scripts/generate_embeddings.py`

**Update `data/templates.json` schema:**
```json
{
  "embedding_dimension": 768,  // Must match global_config.meme_generator.embedding_dimension
  "templates": [
    {
      "template_id": "template_001",
      "name": "Drake Hotline Bling",
      "embedding": [0.123, -0.456, 0.789, ...],  // Length must match embedding_dimension
      ...
    }
  ]
}
```

**Note**: The `embedding_dimension` field serves as validation to catch dimension mismatches early.

### 1.2 In-Memory Semantic Search
**Update `src/services/meme/templates/selector.py`:**
- Load all templates with embeddings into memory
- Validate embedding dimensions match config on startup (fail fast if mismatch)
- Embed the query context using EmbeddingService (dimension from config)
- Calculate cosine similarity in-memory (use numpy)
  - Note: Normalize vectors before cosine similarity (Gemini embeddings at lower dims aren't auto-normalized)
- Sort by similarity score
- Re-rank by tone affinity if specified
- Return top N diverse templates

**Benefits of testing with JSON first:**
- Fast iteration with 5-10 templates
- Validate embedding quality and similarity matching
- Tune similarity thresholds without DB complexity
- Easy to inspect and debug embeddings

---

## Phase 1.5: Database Migration (After embedding validation)

### Goal
Migrate from JSON files to Postgres once basic functionality is proven.

### 1.5.1 Database Schema

**Create Alembic migration for three main tables:**
- `templates`: Stores meme templates with metadata (format, tags, tone_affinity, embeddings, constraints, external_assets)
- `meme_candidates`: Caches generated memes with scores and citations  
- `request_logs`: Tracks API requests for analytics and safety monitoring

### 1.5.2 Migration Script
- Read `data/templates.json`
- Insert all templates into Postgres `templates` table
- Update `src/services/meme/templates/loader.py` → `src/db/utils/template_repository.py`
- Move images from `data/templates/` to Railway storage
- Update `ImageStorage` to use Railway instead of local files

---

## Phase 2: pgvector Migration

### Goal
Migrate embeddings from JSON to Postgres with pgvector for better performance at scale.

### 2.1 pgvector Setup

**CRITICAL: Railway Postgres Requirements**
- Standard Railway Postgres does NOT include pgvector by default
- Must deploy using a pgvector-enabled template from Railway marketplace (e.g., `pgvector-pg18`)
- Cannot simply enable pgvector on existing vanilla Railway Postgres instances

**Setup Steps:**
- Alembic migration to enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- Add embedding column with dimension from config (read `global_config.meme_generator.embedding_dimension` in migration)
- **CRITICAL Migration Warning**:
  - The vector dimension is FIXED once the column is created
  - Changing `global_config.meme_generator.embedding_dimension` after this migration requires:
    1. Creating new column with new dimension
    2. Regenerating ALL embeddings (expensive API calls)
    3. Backfilling new column
    4. Updating all queries
    5. Dropping old column
  - **Recommendation**: Test extensively in Phase 1 (JSON) before committing to a dimension
- Add IVFFlat index for fast cosine similarity search:
  - Syntax: `CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);`
  - Tune `lists` parameter: ~100 for small datasets, `sqrt(num_rows)` for larger datasets
  - Set `ivfflat.probes` at query time to balance speed vs accuracy
  - Don't create index until 1000+ templates (sequential scan is faster for small datasets)

### 2.2 Embedding Migration
- Migrate embeddings from `data/templates.json` to Postgres
- Update `TemplateRepository` to support vector queries

### 2.3 Update Template Selector
- Update `src/services/meme/templates/selector.py` to use pgvector
- Query: Embed context → pgvector cosine similarity search → filter by format/tags
- Keep same logic as Phase 1, but use database instead of in-memory

---

## Phase 3: URL Context & Web Search

### Goal
Add URL ingestion and web search to build richer story briefs.

### 3.1 Enhanced Context Builder
- Update `src/services/meme/context/builder.py`
- Add web search support using Gemini's native grounding with Google Search
  - Enable via `tools: [{"google_search": {}}]` in request
  - Returns structured metadata with web sources and citations
  - Note: Billing applies per grounded query (started Jan 5, 2026)
- Return both StoryBrief and citations list
- Route: URL provided → web search, else → prompt-only

### 3.2 Logo Resolution Service
- Create `src/services/meme/context/logo_service.py`
- Fetch brand logos via logo.dev:
  - Use `img.logo.dev/{domain}?token={LOGO_DEV_PUBLISHABLE_KEY}` for direct image URLs
  - Use `api.logo.dev` with `Authorization: Bearer {LOGO_DEV_SECRET_KEY}` for search/metadata if needed
- Cache results (TTL in config)
- Graceful fallback if logo not found

### 3.3 Asset Resolution in Generator
- Update `src/services/meme/generation/meme_generator.py`
- Resolve logos for templates requiring external assets via LogoService
- Pass logo images directly to nano banana pro as additional image inputs (multimodal, up to 14 total)
- Nano banana pro will integrate logos into the final meme during image generation

---

## Phase 4: Safety Tuning & Sensitive Topics

### Goal
Implement robust safety checks and sensitive topic handling.

### 4.1 Safety Analyzer Service
- Create `src/services/meme/safety/analyzer.py`
- Use DSPYInference with gemini/gemini-3-flash-preview (LLM)
- Decorated with `@observe()` for LangFuse tracing (note the parentheses)
- Pre-generation check: Analyze prompt/URL for policy violations
- Return: is_safe, blocked_reason, safe_alternative suggestion
- Tragedy downgrade: Filter edgy/savage templates for sensitive topics

### 4.2 Orchestrator Integration
- Update `src/services/meme/orchestrator.py`
- Add safety check before context building
- Return 422 error with safe_alternative if blocked
- Apply template downgrade for sensitive topics before generation

---

## Phase 5: Template Management & Admin Features

### Goal
Enable template CRUD operations and admin tools.

### 5.1 Template Admin Routes
- Create `src/api/routes/templates/admin.py`
- `GET /v1/templates`: List templates with filters (format, tags, limit)
- `GET /v1/templates/{template_id}`: Get template details
- `POST /v1/templates`: Create template with auto-embedding generation
- `PATCH /v1/templates/{template_id}`: Update template metadata
- `DELETE /v1/templates/{template_id}`: Soft-delete template
- Use existing auth from `unified_auth.py`

---

## Testing Strategy

### Key Test Areas
- **Unit tests**: Test individual services in `src/services/meme/`
  - `tests/unit/meme/test_context_builder.py`
  - `tests/unit/meme/test_template_selector.py`
  - `tests/unit/meme/test_caption_generator.py`
  - `tests/unit/meme/test_scorer.py`
- **Integration tests**: `tests/integration/test_meme_orchestrator.py`
- **E2E tests**: `tests/e2e/test_meme_generation.py`
  - Follow existing pattern from `tests/e2e/test_ping.py` and `E2ETestBase`
  - Use real Gemini API calls for testing
- **Performance tests**: Latency benchmarks (P50/P95 targets)
- **Safety tests** (Phase 4): Policy violation detection, tragedy downgrade

---

## Deployment Checklist

### Phase 0 Setup (Local JSON iteration)
- [ ] Create `.env` with `GEMINI_API_KEY`
- [ ] Create `data/templates/` and `data/outputs/` directories
- [ ] Ask Eito for 5-10 initial template images
- [ ] Manually annotate templates in `data/templates.json` (without embeddings)
- [ ] Configure LangFuse for LLM observability
- [ ] Install dependencies: `uv add google-genai numpy`

### Phase 1 Setup (Embeddings with JSON)
- [ ] **CRITICAL**: Finalize `embedding_dimension` in `global_config.yaml` (768 recommended for <1000 templates)
- [ ] Run `uv run python -m scripts.generate_embeddings` to add embeddings to JSON
- [ ] Test semantic search quality with 5-10 templates
- [ ] **Experiment with different dimensions** (768 vs 1536 vs 3072) to validate quality vs performance tradeoff
  - Run A/B tests on template selection quality
  - Measure search latency and memory usage
  - **Lock in dimension before Phase 2** - changing later is expensive
- [ ] Tune similarity thresholds and ranking weights

### Phase 1.5+ (Database migration)
- [ ] Add `LOGO_DEV_PUBLISHABLE_KEY` (pk_*) and `LOGO_DEV_SECRET_KEY` (sk_*) to `.env` (note: free tier requires attribution link to logo.dev)
- [ ] Set up Postgres on Railway (use standard template for now, will migrate to pgvector template in Phase 2)
- [ ] Run `alembic upgrade head`
- [ ] Run migration script to import JSON → Postgres (including embeddings)
- [ ] Configure Railway Buckets for image uploads (S3-compatible, private only - use presigned URLs for access)

### Phase 2 (pgvector)
- [ ] **CRITICAL**: Deploy NEW Railway Postgres using pgvector template from marketplace (e.g., `pgvector-pg18`)
- [ ] Migrate data from Phase 1.5 database to pgvector-enabled database using `pg_dump` and restore
- [ ] Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Run pgvector migration
- [ ] Verify vector search performance

### Configuration
- [ ] Update `global_config.yaml` with all settings
- [ ] Set ranking weights and safety defaults
- [ ] Set performance targets and timeouts

### Testing & CI
- [ ] Run `make test`, `make fmt`, `make ruff`, `make vulture`
- [ ] Run `make ci` to verify all checks pass
- [ ] Load test with 10 concurrent requests

### Monitoring
- [ ] Set up LangFuse traces for all LLM calls (gemini/gemini-3-flash-preview with @observe() decorator)
- [ ] Set up LangFuse traces for image generation (gemini-3-pro-image-preview with @observe() decorator)
- [ ] Configure latency alerts (P95 > 25s to account for nano banana pro thinking mode)
- [ ] Track safety refusal rate and template coverage
- [ ] Monitor image generation quality and text rendering accuracy

---

## Implementation Order Summary

1. **Phase 0** (Week 1-2: Basic functionality with JSON)
   - **Ask Eito for 5-10 template images** and annotate in `data/templates.json`
   - Set up folder structure: `src/services/meme/` with subdirectories
   - Core API route: `src/api/routes/meme/generate.py` (follows pattern from `agent.py`)
   - Prompt-only context builder (gemini/gemini-3-flash-preview LLM with `@observe()`)
   - Basic template selection from JSON (filtering, random)
   - Meme generation using Gemini 3 Pro Image (nano banana pro) - takes template + captions + optional logos, outputs final image with superior text rendering
   - LLM-based scoring (gemini/gemini-3-flash-preview with `@observe()`)
   - Local file storage in `data/outputs/`
   - Auth: Reuse `get_authenticated_user` from `unified_auth.py`
   - Rate limiting: Reuse `ensure_daily_limit` from `limits.py` (takes uuid.UUID, not string)

2. **Phase 1** (Week 3: Embeddings & semantic search with JSON)
   - Generate embeddings using Gemini embeddings API
   - Store embeddings in `data/templates.json`
   - Implement in-memory cosine similarity search (numpy)
   - Update template selector to use semantic search
   - **Benefit**: Test and tune embeddings with 5-10 templates before DB complexity

3. **Phase 1.5** (Week 4: Database migration after embedding validation)
   - Database schema + Alembic migrations (follow existing pattern in `alembic/versions/`)
   - Migrate JSON → Postgres (templates + embeddings)
   - Update `loader.py` → `template_repository.py` (follow pattern from `src/db/utils/`)
   - Railway storage integration

4. **Phase 2** (Week 5: pgvector migration)
   - Enable pgvector extension
   - Migrate embeddings to vector column
   - Update selector to use pgvector instead of in-memory search

5. **Phase 3** (Week 6: Richer context)
   - URL context + web search (Gemini)
   - Logo resolution service
   - Citation tracking

6. **Phase 4** (Week 7: Safety)
   - Safety analyzer (gemini/gemini-3-flash-preview LLM with `@observe()`)
   - Sensitive topic detection
   - Template downgrading for tragedies

7. **Phase 5** (Week 8: Admin features)
   - Template CRUD API (new route: `src/api/routes/templates/admin.py`)
   - Admin features
   - Custom template uploads

## Key Patterns to Follow

- **Auth**: Use `get_authenticated_user(request, db)` from `src/api/auth/unified_auth.py` (returns AuthenticatedUser with id and email)
- **Rate Limiting**: Use `ensure_daily_limit(db, user_uuid, limit_name, enforce)` from `src/api/limits.py` (takes uuid.UUID, not string)
- **LLM Calls**: Use `DSPYInference` from `utils/llm/dspy_inference.py` with `@observe()` decorator (note the parentheses)
  - Import: `from langfuse.decorators import observe, langfuse_context`
  - Can update observation name: `langfuse_context.update_current_observation(name="custom-name")`
- **Database**: Use `scoped_session()` and `db_transaction(db)` from `src/db/utils/db_transaction.py`
- **Route Registration**: Add to `src/api/routes/__init__.py` following existing pattern (import router, add to all_routers list)
- **Testing**: Follow `E2ETestBase` pattern from `tests/e2e/e2e_test_base.py`

---

## Open Questions & Decisions Needed

1. **Embedding dimension choice** (MUST DECIDE IN PHASE 1):
   - 768-dim: Faster search, less storage, sufficient for <1000 templates (recommended starting point)
   - 1536-dim: Balanced quality and performance
   - 3072-dim: Full Gemini quality, slower search, more storage
   - **CRITICAL**: This decision is nearly irreversible after Phase 2 migration to pgvector
   - Run quality experiments in Phase 1 (JSON) before committing
2. **Watermark design**: What should the watermark look like? (Note: nano banana pro includes SynthID watermark automatically)
3. **Rate limiting**: Should we add rate limiting at the API gateway level?
4. **Cost tracking**: Should we track per-request costs (LLM + image generation calls)?
5. **Authentication**: Reuse existing API key auth system from agent routes
6. **Prompt engineering**: Fine-tune prompts for nano banana pro to consistently generate meme-style text (bold, white with black stroke, etc.)
7. **Resolution selection**: Should we allow users to specify resolution (1K/2K/4K) or always use default 1K?

---

## Embedding Dimension Recommendation

**For this project, start with 768-dim embeddings:**

**Rationale:**
- Template dataset will likely stay under 1000 templates (even with user uploads)
- 768-dim provides 75% of the quality at 25% of the storage/compute cost vs 3072-dim
- In-memory search with 768-dim vectors is fast enough (<10ms for 1000 templates)
- Gemini embedding quality at 768-dim is sufficient for meme template selection (not mission-critical precision)

**When to consider higher dimensions:**
- If template selection quality is poor in Phase 1 experiments
- If dataset grows beyond 10,000 templates
- If templates become highly similar (need finer-grained distinctions)

**Migration path if dimension change is needed:**
1. Keep old dimension in production
2. Generate new embeddings with new dimension (offline batch job)
3. A/B test both dimensions in production
4. If new dimension performs better, schedule migration
5. Create migration script with validation and rollback plan
6. Execute during low-traffic window

## Next Steps

1. **Ask Eito to provide 5-10 meme template images** for initial dataset
2. Review this plan with the team
3. Set up development environment (`.env`, directories, install Pillow + numpy)
4. Begin Phase 0.0: Template annotation (without embeddings)
5. Begin Phase 0: Core implementation with JSON-based templates
6. Once Phase 0 works, move to Phase 1: Generate embeddings and test semantic search with JSON
   - **CRITICAL**: Experiment with 768/1536/3072 dimensions in Phase 1 before committing
7. After validating embeddings work well, proceed to Phase 1.5: Database migration
