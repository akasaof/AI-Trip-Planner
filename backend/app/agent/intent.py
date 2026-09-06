"""
Intent classification — decides whether an incoming chat message is
trying to change something about the trip (dates, budget, destination,
preferences, add/remove items) versus general conversation (greetings,
thanks, small talk, unrelated questions).

Failure-safe default: if this call fails for any reason (rate limit,
malformed output, etc.), it defaults to "trip_modification" — the safer
failure is an unnecessary replan, not silently ignoring a real
instruction because classification broke.
"""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from app.config import get_settings
from app.agent.prompts.intent import INTENT_SYSTEM_PROMPT




class _IntentResult(BaseModel):
    intent: Literal["trip_modification", "conversation"] = Field(
        description="Whether the message is trying to change the trip, or is just a random conversation or a conversation related to the last plan"
    )


async def classify_intent(message: str) -> Literal["trip_modification", "conversation"]:
    """Classify a chat message's intent. Uses a small, bounded LLM call —
    structured output, low max_tokens, since this is a trivial binary
    decision and doesn't need much room. Defaults to "trip_modification"
    on any failure (see module docstring for why)."""
    settings = get_settings()
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
        max_tokens=100,
    ).with_structured_output(_IntentResult)

    messages = [
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=message),
    ]

    try:
        result: _IntentResult = await llm.ainvoke(messages)
        return result.intent
    except Exception:  # noqa: BLE001 - classification failure should never crash the chat turn;
                        # fall back to the safer default (see module docstring).
        return "trip_modification"