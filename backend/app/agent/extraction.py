# """
# Requirement extraction (spec Section 3, step 2): turns a free-text message
# into a structured TripRequirement, merging with whatever is already known
# about the trip so follow-up messages ("actually 6 days") don't wipe out
# previously-established fields (US-06 / US-07: conversation memory,
# iterative modification).
# """
# """
# Requirement extraction (spec Section 3, step 2): turns a free-text message
# into a structured TripRequirement, merging with whatever is already known
# about the trip so follow-up messages ("actually 6 days") don't wipe out
# previously-established fields (US-06 / US-07: conversation memory,
# iterative modification).

# Dates are extracted as free text ("mid-November", "November 15") rather
# than forced into a strict ISO date field on the LLM's tool schema.
# Groq's structured-output path validates tool-call arguments against the
# JSON schema *before* our code ever sees them, so if the model writes
# "November 15" into a field typed as `date`, the whole call is rejected
# with a 400 — we never get a chance to repair it. Parsing the free text
# ourselves with dateutil, after the call succeeds, is far more robust.
# """
# from datetime import date, datetime, timedelta
# from typing import Optional

# from dateutil import parser as date_parser
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_groq import ChatGroq
# from pydantic import BaseModel, Field

# from app.agent.prompts import EXTRACTION_SYSTEM_PROMPT
# from app.config import get_settings
# from app.models.schemas import TripRequirement


# class _RawTripRequirement(BaseModel):
#     """What we actually ask the LLM for. Same shape as TripRequirement
#     except dates stay as free text — see module docstring."""
#     destination: Optional[str] = None
#     country: Optional[str] = None
#     duration_days: Optional[int] = None
#     travelers: Optional[int] = None
#     budget: Optional[float] = None
#     currency: Optional[str] = "INR"
#     departure_city: Optional[str] = None
#     start_date_text: Optional[str] = Field(
#         default=None, description="Trip start date exactly as the traveler expressed it, e.g. "
#                                    "'November 15', 'mid-November', '2026-11-15'. Do not reformat it."
#     )
#     end_date_text: Optional[str] = Field(
#         default=None, description="Trip end date exactly as the traveler expressed it, if given."
#     )
#     preferences: list[str] = Field(default_factory=list)
#     trip_type: Optional[str] = None


# def _get_extraction_llm() -> ChatGroq:
#     settings = get_settings()
#     llm = ChatGroq(
#         model=settings.groq_model,
#         api_key=settings.groq_api_key,
#         temperature=0,
#     )
#     return llm.with_structured_output(_RawTripRequirement)


# def _parse_fuzzy_date(text: str | None, today: date) -> date | None:
#     """Best-effort parse of a human-written date. Never raises — returns
#     None if it genuinely can't make sense of it, so the caller can ask
#     the traveler to clarify rather than silently inventing a date."""
#     if not text or not text.strip():
#         return None
#     # "mid-November" / "early December" etc. aren't parseable as-is; take
#     # a representative day so the trip still has *a* concrete date to plan
#     # around, rather than failing entirely.
#     normalized = (
#         text.strip()
#         .replace("mid-", "")
#         .replace("early ", "")
#         .replace("late ", "")
#     )
#     try:
#         parsed = date_parser.parse(normalized, fuzzy=True, default=datetime(today.year, today.month, 1))
#     except (ValueError, OverflowError):
#         return None
#     result = parsed.date()
#     # If the parsed month/day has already passed this year and no year was
#     # explicitly stated, assume the traveler means the next occurrence.
#     if result < today and str(today.year) not in text:
#         try:
#             result = result.replace(year=today.year + 1)
#         except ValueError:  # Feb 29 on a non-leap next year, etc.
#             pass
#     return result


# async def extract_requirement(
#     message: str,
#     prior: TripRequirement | None = None,
# ) -> TripRequirement:
#     prior = prior or TripRequirement()
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", EXTRACTION_SYSTEM_PROMPT),
#         ("human",
#          "Previously known trip fields (JSON, may be partially empty):\n{prior}\n\n"
#          "Traveler's new message:\n{message}\n\n"
#          "Return the FULL updated set of fields, keeping anything unaffected by the new "
#          "message unchanged from the previous fields."),
#     ])
#     chain = prompt | _get_extraction_llm()

#     try:
#         result: _RawTripRequirement = await chain.ainvoke({
#             "prior": prior.model_dump_json(),
#             "message": message,
#         })
#     except Exception:  # noqa: BLE001 - a malformed/oversized tool call, rate limit, etc. should
#                         # never crash the whole chat turn. Fall back to whatever we already knew;
#                         # the router will ask for anything still missing.
#         return prior

#     today = date.today()
#     start_date = _parse_fuzzy_date(result.start_date_text, today) or prior.start_date
#     end_date = _parse_fuzzy_date(result.end_date_text, today) or prior.end_date

#     # If we only have an end date and a duration, back-fill the start date
#     # (and vice versa) rather than leaving a gap the user already closed.
#     duration_days = result.duration_days or prior.duration_days
#     if start_date and not end_date and duration_days:
#         end_date = start_date + timedelta(days=duration_days - 1)
#     elif end_date and not start_date and duration_days:
#         start_date = end_date - timedelta(days=duration_days - 1)

#     # If the traveler gave BOTH an explicit start and end date, that's
#     # unambiguous ground truth — recompute duration_days from the actual
#     # span rather than trusting a duration_days figure from an earlier
#     # message that may now be inconsistent with it (e.g. "5-day trip"
#     # followed later by an explicit "Nov 15 to Nov 21" date range, which
#     # actually spans 7 days).
#     if start_date and end_date and end_date >= start_date:
#         duration_days = (end_date - start_date).days + 1

#     new_data = result.model_dump(exclude={"start_date_text", "end_date_text"})
#     new_data["start_date"] = start_date
#     new_data["end_date"] = end_date
#     new_data["duration_days"] = duration_days

#     # Belt-and-braces merge in case the model drops a field it shouldn't have touched.
#     merged_data = prior.model_dump()
#     for key, value in new_data.items():
#         if value not in (None, [], ""):
#             merged_data[key] = value
#     return TripRequirement(**merged_data)



"""
Requirement extraction (spec Section 3, step 2): turns a free-text message
into a structured TripRequirement, merging with whatever is already known
about the trip so follow-up messages ("actually 6 days") don't wipe out
previously-established fields (US-06 / US-07: conversation memory,
iterative modification).
"""
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as date_parser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.agent.prompts import EXTRACTION_SYSTEM_PROMPT
from app.config import get_settings
from app.models.schemas import TripRequirement


class _RawTripRequirement(BaseModel):
    destination: Optional[str] = None
    country: Optional[str] = None
    duration_days: Optional[int] = None
    travelers: Optional[int] = None
    budget: Optional[float] = None
    currency: Optional[str] = "INR"
    departure_city: Optional[str] = None
    start_date_text: Optional[str] = Field(
        default=None,
        description="Trip start date exactly as traveler expressed it e.g. 'November 15', 'mid-November'."
    )
    end_date_text: Optional[str] = Field(
        default=None,
        description="Trip end date exactly as traveler expressed it."
    )
    preferences: list[str] = Field(default_factory=list)
    trip_type: Optional[str] = None


def _get_extraction_llm() -> ChatGroq:
    settings = get_settings()
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
    )
    return llm.with_structured_output(_RawTripRequirement)


def _parse_fuzzy_date(text: str | None, today: date) -> date | None:
    if not text or not text.strip():
        return None
    normalized = (
        text.strip()
        .replace("mid-", "")
        .replace("early ", "")
        .replace("late ", "")
    )
    try:
        parsed = date_parser.parse(normalized, fuzzy=True, default=datetime(today.year, today.month, 1))
    except (ValueError, OverflowError):
        return None
    result = parsed.date()
    if result < today and str(today.year) not in text:
        try:
            result = result.replace(year=today.year + 1)
        except ValueError:
            pass
    return result


async def extract_requirement(
    message: str,
    prior: TripRequirement | None = None,
) -> TripRequirement:
    prior = prior or TripRequirement()
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human",
         "Previously known trip fields (JSON):\n{prior}\n\n"
         "Traveler's new message:\n{message}\n\n"
         "Return the FULL updated set of fields. If the traveler changed duration or dates, "
         "update duration_days accordingly."),
    ])
    chain = prompt | _get_extraction_llm()

    try:
        result: _RawTripRequirement = await chain.ainvoke({
            "prior": prior.model_dump_json(),
            "message": message,
        })
    except Exception:  # noqa: BLE001
        return prior

    today = date.today()
    parsed_start = _parse_fuzzy_date(result.start_date_text, today)
    parsed_end = _parse_fuzzy_date(result.end_date_text, today)

    # 1. Start and End date resolution
    start_date = parsed_start or prior.start_date
    end_date = parsed_end or prior.end_date
    duration_days = result.duration_days or prior.duration_days

    # 2. Handle duration updates vs explicit date changes
    if parsed_start and parsed_end and parsed_end >= parsed_start:
        # User provided explicit new date bounds
        duration_days = (parsed_end - parsed_start).days + 1
    elif result.duration_days and result.duration_days != prior.duration_days:
        # User changed duration (e.g., "make it a 3 day trip") -> shift end_date relative to start_date
        duration_days = result.duration_days
        if start_date:
            end_date = start_date + timedelta(days=duration_days - 1)
    elif start_date and duration_days:
        end_date = start_date + timedelta(days=duration_days - 1)

    # 3. Preferences merging (append new non-duplicate preferences)
    existing_prefs = set(prior.preferences or [])
    new_prefs = set(result.preferences or [])
    merged_preferences = list(existing_prefs.union(new_prefs))

    # 4. Construct final dict using prior state as baseline
    merged_data = prior.model_dump()
    new_data = result.model_dump(exclude={"start_date_text", "end_date_text", "preferences"})
    
    for key, value in new_data.items():
        if value not in (None, [], ""):
            merged_data[key] = value

    merged_data["start_date"] = start_date
    merged_data["end_date"] = end_date
    merged_data["duration_days"] = duration_days
    merged_data["preferences"] = merged_preferences

    return TripRequirement(**merged_data)