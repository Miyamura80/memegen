# PRD: Context-Aware Meme Generator API

## 1. Summary

Build an API that generates **N meme candidates** (default 10) from **freeform text** and optionally a **news/article URL**. The system fetches and summarizes the broader story, selects best-fit meme templates from a template database, and renders candidate memes with captions.

## 2. Goals

* Turn a prompt + (optional) URL into **multiple high-quality meme options**.
* Ground memes in **accurate, current context** when a URL is provided.
* Provide predictable latency and cost controls (configurable N, context depth, render sizes).
* Enable a growing **meme template catalog** with metadata, examples, and constraints.

## 3. Non-goals

* Building a full social posting tool.
* Long-form satire writing or political persuasion tooling.
* Copyright-unsafe distribution of proprietary images (templates must be licensed/allowed).

## 4. Users & Use Cases

### 4.1 Users

* Devs building meme tools, community bots, newsroom engagement widgets.
* Social teams wanting quick variants.

### 4.2 Use cases

* **News meme**: user provides article URL + instruction (tone, target, constraints).
* **Prompt-only meme**: user provides situation or joke premise.
* **Brand-safe meme**: user requests no profanity, no harassment, neutral tone.

## 5. User Stories

* As a developer, I send a URL + text prompt and get 10 meme images + captions.
* As a developer, I can ask for fewer candidates to reduce cost.
* As a developer, I can request only certain template families (e.g., "reaction" vs "two-panel").
* As a developer, I can pass a safety mode (strict/standard) and get compliant output.

## 6. Functional Requirements

### 6.1 Inputs

**Required**

* `prompt`: freeform text.

**Optional**

* `url`: article link.
* `num_candidates` (default 10, max e.g. 25).
* `tone`: {dry, wholesome, savage, absurdist, neutral}.
* `audience`: {general, tech, finance, sports, …}.
* `style`: {classic-impact, modern, minimal}.
* `safety_mode`: {strict, standard}.
* `template_filters`:

  * `include_tags`, `exclude_tags`
  * `template_ids`
  * `format`: {single, two-panel, four-panel, caption-only}
* `render`:

  * `size`: {512, 768, 1024}
  * `format`: {png, jpg, webp}
  * `watermark`: boolean
* `language` (default en)

### 6.2 Outputs

Return a ranked list of candidates with:

* `candidate_id`
* `template_id`, `template_name`
* `captions`: per text box (array)
* `image_url` (or base64 if requested)
* `alt_text`
* `explanation` (short: why this template fits)
* `scores`: humor, relevance, clarity, safety, originality (0-1)
* `citations` (when URL used): list of sources used for context
* `trace_id`

### 6.3 Context builder (Step 1)

Context retrieval is handled via an external **LLM with built-in web search** (e.g. OpenAI). We do **not** implement a first-party URL fetcher or crawler in v1.

* The `url`, if provided, is treated as **part of the prompt** passed to the LLM.
* The LLM is responsible for searching, aggregating sources, and producing a story brief.

**Conditional asset resolution**

* As part of the story brief, the LLM may flag required **brands, companies, or products**.
* If a selected template requires a logo, the system fetches it on-demand via **logo.dev**.
* Logo fetching is **best-effort** and does not run for every request.

Outputs a structured **story brief**:

* who / what / when / where
* key events
* main tension or contrast
* notable reactions or narratives
* key named entities
* optional `required_assets` (e.g. logos)

If no `url`:

* Build a smaller "prompt brief": entities, scenario, sentiment, implied target.

### 6.4 Template selection (Step 2)

Maintain a **template DB** where fields are explicitly optional vs required.

**Required fields**

* `template_id`
* `name`
* `base_image` (or prompt reference for generation)
* `format` (single-panel, two-panel, multi-panel, freeform)

**Optional fields**

* `text_boxes` (JSON):

  * only required for rigid formats (e.g. classic Impact memes)
  * may be omitted for freeform or image-generation-based templates
* `tags` (reaction, comparison, cope, win, loss, bureaucracy, etc.)
* `tone_affinity`
* `example_uses`
* `constraints` (e.g. avoid tragedy, max text length)
* `external_assets`:

  * logos or brands required by the meme
  * resolved on the fly via **logo.dev** when needed

**Selection flow**

1. Embed story brief + prompt.
2. Retrieve candidate templates via semantic match on name, tags, examples.
3. Filter by format and constraints.
4. Re-rank by tone fit and novelty.

### 6.5 Candidate generation (Step 2)

**V1 simplification**

* Do **not** separately generate captions.
* Use **Google Nano Banana Pro API** to generate the final meme image directly.

Inputs to image generation:

* story brief
* selected template (image or template description)
* any resolved external assets (e.g. logos)
* high-level instruction (tone, audience, safety mode)

For each template:

* Generate 1 image per template (no caption drafts).
* Still produce metadata:

  * short explanation
  * scores (LLM-evaluated)

### 6.6 Rendering (Step 3)

**V1 approach**

* Rendering is handled entirely by **Nano Banana Pro**.
* No internal text layout engine.
* Output is a fully rendered image returned by the model.

Post-processing:

* Optional watermark
* Format conversion (png/jpg/webp)
* Upload to object storage and return signed URLs

### 6.7 Configurable ranking

Ranking logic must be **fully configuration-driven**.

* Ranking weights stored in config (not code).
* Allow per-request override of weights.
* Allow swapping scoring prompts without redeploy.

Default score aggregation:
```
S = w_r*relevance + w_h*humor + w_c*clarity + w_o*originality + w_s*safety
```

## 7. Safety & Policy Requirements

* Disallow hateful harassment, targeted abuse, sexual content with minors, self-harm encouragement, doxxing.
* If `url` involves tragedy/violence: downgrade "edgy" templates; prefer neutral/wholesome tone.
* Provide `blocked_reason` and safe alternatives when output is refused.
* Content provenance: store URL fetch logs and citations (redact PII).

## 8. API Design

### 8.1 Endpoints

* `POST /v1/memes/generate`
* `GET /v1/memes/{candidate_id}` (metadata)
* `GET /v1/templates` (list, filter)
* `GET /v1/templates/{template_id}`

### 8.2 Example request

```json
{
  "prompt": "Make memes about regulators panicking over AI deepfakes",
  "url": "https://example.com/news/article",
  "num_candidates": 10,
  "tone": "dry",
  "safety_mode": "standard",
  "render": {"size": 768, "format": "png"}
}
```

### 8.3 Example response (shape)

```json
{
  "trace_id": "tr_...",
  "candidates": [
    {
      "candidate_id": "m_...",
      "template_id": "t_drake",
      "template_name": "Drake Hotline Bling",
      "captions": ["Manual ID checks", "Cryptographic provenance"],
      "image_url": "https://...signed...",
      "alt_text": "Drake rejects manual ID checks and approves cryptographic provenance.",
      "explanation": "Two-option contrast fits the policy tradeoff in the story.",
      "scores": {"humor": 0.71, "relevance": 0.83, "clarity": 0.90, "safety": 0.98, "originality": 0.55},
      "citations": ["..." ]
    }
  ]
}
```

## 9. System Architecture

### 9.1 Components

* **API Gateway** (auth/keys/usage handled by template repo)
* **Context Builder Service**

  * URL fetcher
  * Search + multi-source summarizer
  * Story brief generator
* **Template Service**

  * template DB
  * retrieval + ranking
* **Caption Generator**

  * constraint-aware captioning
  * safety filtering
* **Renderer**

  * text layout engine
  * asset storage + signed URLs
* **Observability**

  * traces per request, model usage, failures

### 9.2 Data stores

* Template DB (Postgres)
* Template assets (object storage)
* Analytics store (existing)

**No caching layer in v1.**

## 10. Template Database Spec

### 10.1 Table: `templates`

* `template_id` (PK)
* `name`
* `image_uri`
* `format` (single/two/four)
* `text_boxes` (JSON: coords, max_chars, alignment)
* `tags` (array)
* `tone_affinity` (array)
* `safety_flags` (array)
* `example_captions` (JSON)
* `license` (enum + attribution)
* `created_at`, `updated_at`

### 10.2 Indexing

* Vector embeddings for `name`, `tags`, `examples`, and "use pattern".
* Standard indices on tags/format.

## 11. Ranking & Quality

### 11.1 Scoring models

All scoring is performed via **LLMs**.

* Each score dimension uses a separate prompt.
* Prompts are stored as versioned files (not hard-coded).
* Scores normalized to [0, 1].

No learned or heuristic models in v1.

### 11.2 Diversity requirement

* Do not return multiple candidates using the **same exact template** unless explicitly requested.
* Diversity is enforced at the template level only.

(No notion of "template families" in v1.)

### 11.3 Guardrails

* Safety handled by upstream LLM policies + our post-checks.
* No special handling for paywalled articles.
* URL reliability is delegated entirely to the external search-enabled LLM.

## 12. Performance Targets

* P50 latency: 4-8s (prompt-only)
* P50 latency: 8-15s (URL + search)
* Hard timeout: 25s default (configurable)
* Cost controls:

  * cap web sources K
  * cap templates M
  * cap candidates N

## 13. Error Handling

* `400` invalid input, unsupported URL
* `402` quota exceeded (handled by template repo)
* `408` timeout: return partial candidates with warning
* `422` unsafe content: return refusal + safe suggestions
* `500` internal

Return shape should support partial success:

* `warnings`: ["url_fetch_failed", "used_search_only"]

## 14. Logging & Privacy

* Store:

  * request params (redact prompt if user opts out)
  * fetched URLs + timestamps
  * citations list
  * template IDs used
  * safety decisions
* Do not store:

  * full fetched article text long-term (store hash + brief)

## 15. Metrics

* Success rate
* Latency P50/P95
* Avg candidates generated per request
* Safety refusal rate
* User engagement proxy (if available): clicks/downloads
* Template coverage: how often each template is selected

## 16. Rollout Plan

* Phase 0: Prompt-only, small template set, basic rendering.
* Phase 1: URL ingestion + search-based story brief.
* Phase 2: Template DB + embeddings + diversity ranking.
* Phase 3: Safety tuning + sensitive-topic handling.
* Phase 4: Custom template uploads (enterprise).

## 17. Open Questions

* Which LLM providers to support at launch.
* Cost vs latency trade-offs for image generation.
* How many templates are needed for acceptable coverage at v1.
