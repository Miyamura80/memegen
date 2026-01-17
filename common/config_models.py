"""
Pydantic models for global configuration structure.
This module defines all the nested configuration models used by the Config class.
Each model corresponds to a section in the global_config.yaml file and provides
type validation and structure for the configuration data.
"""

from pydantic import BaseModel


class ExampleParent(BaseModel):
    """Example configuration parent model."""

    example_child: str


class DefaultLlm(BaseModel):
    """Default LLM configuration."""

    default_model: str
    fast_model: str
    cheap_model: str
    default_temperature: float
    default_max_tokens: int


class RetryConfig(BaseModel):
    """Retry configuration for LLM requests."""

    max_attempts: int
    min_wait_seconds: int
    max_wait_seconds: int


class TimeoutConfig(BaseModel):
    """Timeout configuration for LLM API requests."""

    api_timeout_seconds: int
    connect_timeout_seconds: int


class LlmConfig(BaseModel):
    """LLM configuration including caching and retry settings."""

    cache_enabled: bool
    retry: RetryConfig
    timeout: TimeoutConfig


class LoggingLocationConfig(BaseModel):
    """Location information display configuration for logging."""

    enabled: bool
    show_file: bool
    show_function: bool
    show_line: bool
    show_for_info: bool
    show_for_debug: bool
    show_for_warning: bool
    show_for_error: bool


class LoggingFormatConfig(BaseModel):
    """Logging format configuration."""

    show_time: bool
    show_session_id: bool
    location: LoggingLocationConfig


class LoggingLevelsConfig(BaseModel):
    """Logging level configuration."""

    debug: bool
    info: bool
    warning: bool
    error: bool
    critical: bool


class LoggingConfig(BaseModel):
    """Complete logging configuration."""

    verbose: bool
    format: LoggingFormatConfig
    levels: LoggingLevelsConfig


class StreamingConfig(BaseModel):
    """Streaming configuration for agent chat."""

    heartbeat_interval_seconds: int
    first_token_timeout_seconds: int
    max_streaming_duration_seconds: int


class AgentChatConfig(BaseModel):
    """Agent chat configuration."""

    history_message_limit: int
    streaming: StreamingConfig


class StripePriceIdsConfig(BaseModel):
    """Stripe price IDs configuration."""

    test: str
    prod: str


class SubscriptionStripeConfig(BaseModel):
    """Subscription Stripe configuration."""

    price_ids: StripePriceIdsConfig


class MeteredConfig(BaseModel):
    """Metered billing configuration."""

    included_units: int
    overage_unit_amount: int
    unit_label: str


class PaymentRetryConfig(BaseModel):
    """Payment retry configuration."""

    max_attempts: int


class SubscriptionConfig(BaseModel):
    """Subscription configuration."""

    stripe: SubscriptionStripeConfig
    metered: MeteredConfig
    trial_period_days: int
    payment_retry: PaymentRetryConfig


class StripeWebhookConfig(BaseModel):
    """Stripe webhook configuration."""

    url: str


class StripeConfig(BaseModel):
    """Stripe configuration."""

    api_version: str
    webhook: StripeWebhookConfig


class TelegramChatIdsConfig(BaseModel):
    """Telegram chat IDs configuration."""

    admin_alerts: str
    test: str


class TelegramConfig(BaseModel):
    """Telegram configuration."""

    chat_ids: TelegramChatIdsConfig


class ServerConfig(BaseModel):
    """Server configuration."""

    allowed_origins: list[str]


class MemeGeneratorConfig(BaseModel):
    """Meme generator configuration."""

    default_num_candidates: int
    max_candidates: int
    default_timeout: int
    default_resolution: str
    default_render_format: str
    prompt_only_p50_target: int
    url_based_p50_target: int
    max_web_sources: int
    max_templates_per_request: int
    max_reference_images: int
    embedding_dimension: int


class GeminiConfig(BaseModel):
    """Gemini provider configuration."""

    default_model: str
    image_generation_model: str
    enable_web_search: bool
    embedding_model: str


class LlmProvidersConfig(BaseModel):
    """LLM providers configuration."""

    gemini: GeminiConfig


class LogoServiceConfig(BaseModel):
    """Logo service configuration."""

    image_base_url: str
    api_base_url: str
    cache_ttl: int


class ObjectStorageConfig(BaseModel):
    """Object storage configuration."""

    provider: str
    bucket: str
    signed_url_expiry: int


class RankingWeightsConfig(BaseModel):
    """Ranking weights configuration."""

    relevance: float
    humor: float
    clarity: float
    originality: float
    safety: float


class RankingConfig(BaseModel):
    """Ranking configuration."""

    weights: RankingWeightsConfig
    allow_per_request_override: bool


class SafetyConfig(BaseModel):
    """Safety configuration."""

    default_mode: str
    strict_mode_templates: list[str]
    blocked_tags: list[str]
