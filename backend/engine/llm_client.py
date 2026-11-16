"""
LiteLLM boundary: one chat completion through the user's LiteLLM proxy.

`litellm` is imported on first use only: it is heavy, and the application must
start (and keep its memory) when the NL->rule feature is disabled.
"""
import asyncio
import logging
import math
import os
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Dict, List, Protocol

logger = logging.getLogger(__name__)

# Maximum duration of one provider call, and of the whole call including connection
LLM_TIMEOUT_SECONDS = 20
MAX_OUTPUT_TOKENS = 1500

# Price applied only when LiteLLM cannot price the model (a custom proxy alias):
# deliberately high so that the hard budget cap errs on the safe side.
UNPRICED_USD_PER_1M_TOKENS = 15.0
CHARS_PER_TOKEN = 4

LITELLM_LOGGERS = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")

# The proxy speaks the OpenAI protocol: litellm is told so explicitly, so the model
# name is the bare alias of the proxy and needs no provider prefix.
PROXY_PROVIDER = "openai"
# Older deployments set LITELLM_MODEL to "openai/<alias>" (litellm's way of choosing
# the provider through the name); that one leading prefix is still accepted.
LEGACY_MODEL_PREFIX = "openai/"

Message = Dict[str, str]


class LlmError(Exception):
    """The provider failed (network, timeout, HTTP error or malformed answer)."""


@dataclass(frozen=True)
class LlmSettings:
    """Connection settings of the LiteLLM proxy."""

    api_key: str = field(repr=False)
    base_url: str
    model: str


@dataclass(frozen=True)
class LlmReply:
    """Text answer of the model and its estimated cost."""

    content: str
    cost_usd: float


class LlmClient(Protocol):
    """Anything able to answer a chat conversation."""

    async def complete(self, messages: List[Message]) -> LlmReply:
        """Return the model answer to the conversation."""


def proxy_model_name(model: str) -> str:
    """The model name to send to the proxy: its alias, without a legacy `openai/` prefix.

    Only one leading prefix is removed, so `openai/openai/x` becomes `openai/x`.

    Args:
        model: Value of LITELLM_MODEL.

    Returns:
        The alias the proxy receives.
    """
    return model.removeprefix(LEGACY_MODEL_PREFIX)


@cache
def load_litellm() -> Any:
    """Import litellm once, without letting it download its price table.

    LITELLM_LOCAL_MODEL_COST_MAP makes litellm use the price table bundled with
    the package instead of fetching it from GitHub at import time.
    """
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    # The prompt holds untrusted user text and the answer is business data:
    # neither may reach litellm's logs or callbacks.
    litellm.turn_off_message_logging = True
    for name in LITELLM_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, logging.getLogger(name).level))
    return litellm


def estimate_cost_usd(litellm_module: Any, response: Any, messages: List[Message], content: str) -> float:
    """Estimate the cost of one completion.

    Uses `litellm.completion_cost` when it can price the response; otherwise
    falls back to a token count (provider usage, or characters / 4) at
    UNPRICED_USD_PER_1M_TOKENS.

    Args:
        litellm_module: The imported litellm module.
        response: Completion response returned by litellm.
        messages: Conversation sent to the model.
        content: Text answer of the model.

    Returns:
        Cost in USD, strictly positive.
    """
    try:
        cost = litellm_module.completion_cost(completion_response=response)
    except Exception:  # litellm raises a plain Exception for models it cannot price
        cost = None
    if cost and cost > 0:
        return float(cost)

    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if not isinstance(total_tokens, int) or total_tokens <= 0:
        characters = sum(len(message["content"]) for message in messages) + len(content)
        total_tokens = max(1, math.ceil(characters / CHARS_PER_TOKEN))
    return total_tokens * UNPRICED_USD_PER_1M_TOKENS / 1_000_000


def estimate_input_cost_usd(messages: List[Message]) -> float:
    """Pessimistic cost of a request that was sent but never answered.

    The provider may have billed the prompt even though the call failed or timed
    out: characters / 4 tokens at UNPRICED_USD_PER_1M_TOKENS, output ignored.

    Args:
        messages: Conversation sent to the model.

    Returns:
        Cost in USD, strictly positive.
    """
    characters = sum(len(message["content"]) for message in messages)
    tokens = max(1, math.ceil(characters / CHARS_PER_TOKEN))
    return tokens * UNPRICED_USD_PER_1M_TOKENS / 1_000_000


def estimate_reservation_usd(messages: List[Message]) -> float:
    """Cost to reserve before a call: the prompt plus a full-length answer.

    Same pessimistic rate as `estimate_input_cost_usd`. The reservation is
    replaced by the real cost once the call ends.

    Args:
        messages: Conversation about to be sent.

    Returns:
        Cost in USD, strictly positive.
    """
    characters = sum(len(message["content"]) for message in messages)
    tokens = max(1, math.ceil(characters / CHARS_PER_TOKEN)) + MAX_OUTPUT_TOKENS
    return tokens * UNPRICED_USD_PER_1M_TOKENS / 1_000_000


class LiteLLMClient:
    """Chat completion through LiteLLM, pointed at the configured proxy."""

    def __init__(self, settings: LlmSettings) -> None:
        """Create the client.

        Args:
            settings: Proxy URL, API key and model (the alias defined on the proxy).
        """
        self._settings = settings

    async def complete(self, messages: List[Message]) -> LlmReply:
        """Send the conversation and return the answer with its cost.

        Args:
            messages: Chat messages (role and content).

        Returns:
            The text answer and its estimated cost.

        Raises:
            LlmError: On any provider failure or unusable answer. Details go to
                the logs (class name only: provider messages may echo the prompt).
        """
        litellm = load_litellm()

        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=proxy_model_name(self._settings.model),
                    custom_llm_provider=PROXY_PROVIDER,
                    messages=messages,
                    api_key=self._settings.api_key,
                    api_base=self._settings.base_url,
                    temperature=0,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    response_format={"type": "json_object"},
                    timeout=LLM_TIMEOUT_SECONDS,
                    num_retries=0,
                    drop_params=True,
                ),
                timeout=LLM_TIMEOUT_SECONDS + 5,
            )
            content = response.choices[0].message.content or ""
        except Exception as exc:  # litellm raises its own hierarchy plus provider-specific errors
            logger.warning("LLM call failed: %s", type(exc).__name__)
            raise LlmError("LLM call failed") from exc

        return LlmReply(content=content, cost_usd=estimate_cost_usd(litellm, response, messages, content))
