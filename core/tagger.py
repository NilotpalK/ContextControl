import json
import re
import requests
from typing import Optional

from config import (
    OPENROUTER_BASE_URL,
    OPENROUTER_API_KEY,
    TAGGER_MODEL,
    CONFIDENCE_THRESHOLD,
    CHAIN_REFERENCE_KEYWORDS,
)
from models import TagResult
from db.sqlite import get_topic_names, get_session_exchanges, get_last_exchange


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_prompt(
    user_turn: str,
    asst_turn: str,
    existing_topics: list[str],
    recent_exchanges: list,
) -> str:

    # Check for reference keywords as a hint for the model
    has_reference_hint = any(
        kw in user_turn.lower()
        for kw in CHAIN_REFERENCE_KEYWORDS
    )

    # Build recent exchange context string
    recent_context = ""
    for i, ex in enumerate(recent_exchanges[-3:]):
        recent_context += f"Exchange {i+1}:\n"
        recent_context += f"  User: {ex['user_turn'][:200]}\n"
        recent_context += f"  Assistant: {ex['asst_turn'][:200]}\n\n"

    topics_str = ", ".join(existing_topics) if existing_topics else "none yet"

    prompt = f"""You are a conversation topic tagger. Analyze the exchange below and return structured JSON metadata.

EXISTING TOPICS IN THIS SESSION:
{topics_str}

RECENT EXCHANGES FOR CONTEXT:
{recent_context if recent_context else "This is the first exchange."}

CURRENT EXCHANGE TO TAG:
User: {user_turn}
Assistant: {asst_turn}

REFERENCE HINT: Reference keywords {'WERE' if has_reference_hint else 'were NOT'} detected in the user message. Check carefully regardless.

INSTRUCTIONS:
1. Identify the primary topic of this exchange
2. If the topic already exists in EXISTING TOPICS use that EXACT name — do not create a variation
3. If it is new, name it after the SPECIFIC technology or tool being discussed (e.g. "Postgres Setup", "MongoDB Indexing", "React Hooks") — NEVER use generic names like "Database Setup" or "Framework Usage"
4. Infer the parent category (e.g. "Postgres" -> "Databases", "MongoDB" -> "Databases", "React" -> "Frontend")
5. Check if this exchange references a previous exchange in RECENT EXCHANGES FOR CONTEXT. Use the exchange number (1, 2, or 3) in references_exchange_id if it references one. If the topic changes completely and there is NO reference, you MUST set references_exchange_id to null.
6. Determine if the topic is just a passing mention or the main focus
7. Rate your confidence from 0.0 to 1.0

Return ONLY a valid JSON object, no explanation, no markdown:
{{
  "primary_topic": "string",
  "parent_topic": "string or null",
  "is_new_topic": true or false,
  "mentions": ["list", "of", "other", "concepts", "mentioned"],
  "references_exchange_id": null,
  "reference_type": "direct or implicit or null",
  "is_passing_mention": true or false,
  "confidence": 0.0 to 1.0
}}"""

    return prompt



# ── OpenRouter caller ──────────────────────────────────────────────────────────

def call_openrouter(prompt: str) -> str:
    """Send prompt to OpenRouter and return raw text response."""
    response = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": TAGGER_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 300,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")


# ── JSON extractor ─────────────────────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """
    Extract JSON from model response.
    Models sometimes wrap JSON in markdown fences — this handles that.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Find the first { and last } to isolate JSON
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")

    return json.loads(text[start:end])


# ── Fallback ───────────────────────────────────────────────────────────────────

def get_fallback_tag(session_id: str) -> TagResult:
    """
    Called when confidence is below threshold or parsing fails.
    Falls back to the last known active topic for this session.
    If no prior exchanges exist, returns a generic Uncategorized tag.
    """
    last = get_last_exchange(session_id)
    if last:
        from db.sqlite import get_topics_for_exchange
        topics = get_topics_for_exchange(last["id"])
        if topics:
            return TagResult(
                primary_topic=topics[0],
                confidence=0.0,
                is_new_topic=False,
                is_passing_mention=False,
            )
    return TagResult(
        primary_topic="Uncategorized",
        confidence=0.0,
        is_new_topic=True,
        is_passing_mention=False,
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def tag_exchange(
    user_turn: str,
    asst_turn: str,
    session_id: str,
    exchange_id: Optional[str] = None,
) -> TagResult:
    """
    Tag an exchange with topic metadata.
    Returns a TagResult pydantic model.
    Falls back gracefully on low confidence or any error.

    exchange_id should be passed when the exchange has already been persisted
    before tagging (as in the /exchange pipeline) so we can exclude it from
    the recent-context window and avoid the model self-referencing.
    """
    existing_topics  = get_topic_names(session_id)
    all_recent       = get_session_exchanges(session_id, include_hidden=True)

    # Exclude the current exchange from the context window so the model
    # cannot pick it as a chain-reference target.
    if exchange_id:
        recent_exchanges = [ex for ex in all_recent if ex["id"] != exchange_id]
    else:
        recent_exchanges = all_recent

    prompt = build_prompt(
        user_turn=user_turn,
        asst_turn=asst_turn,
        existing_topics=existing_topics,
        recent_exchanges=recent_exchanges,
    )

    try:
        raw  = call_openrouter(prompt)
        data = extract_json(raw)

        # ── Resolve references_exchange_id ───────────────────────────────────
        # The model receives recent exchanges numbered 1, 2, 3 in the prompt.
        # It often returns references_exchange_id as an integer positional index
        # rather than a real UUID. Resolve it to the actual exchange ID here.
        ref_raw = data.get("references_exchange_id")
        resolved_ref: Optional[str] = None

        if ref_raw is not None:
            # Model returned an integer index (1-based, last 3 exchanges)
            if isinstance(ref_raw, int):
                window = recent_exchanges[-3:]   # same slice used in prompt
                idx = ref_raw - 1               # convert 1-based to 0-based
                if 0 <= idx < len(window):
                    resolved_ref = window[idx]["id"]
                    # Guard against self-references
                    if exchange_id and resolved_ref == exchange_id:
                        print(f"[tagger] Discarding self-reference at index {ref_raw}")
                        resolved_ref = None
                    else:
                        print(f"[tagger] Resolved ref index {ref_raw} → {resolved_ref}")
                else:
                    print(f"[tagger] Ref index {ref_raw} out of range (window={len(window)})")
            elif isinstance(ref_raw, str) and ref_raw.startswith("exchange_"):
                # Already looks like a real exchange ID
                resolved_ref = ref_raw
            else:
                print(f"[tagger] Unrecognised references_exchange_id format: {ref_raw!r} — ignoring")

        data["references_exchange_id"] = resolved_ref

        # ── Ensure confidence is a float ─────────────────────────────────────
        try:
            data["confidence"] = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            data["confidence"] = 0.0

        result = TagResult(**data)

        # Confidence check — fall back if model is not sure enough
        if result.confidence < CONFIDENCE_THRESHOLD:
            print(f"[tagger] Low confidence ({result.confidence}) — using fallback")
            return get_fallback_tag(session_id)

        return result

    except Exception as e:
        print(f"[tagger] Error: {e} — using fallback")
        return get_fallback_tag(session_id)