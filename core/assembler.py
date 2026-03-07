from config import MAX_EXCHANGES_IN_CONTEXT, MAX_TOKENS_CONTEXT
from models import Exchange, ContextResponse
from db.sqlite import (
    get_session_exchanges,
    get_hidden_topics,
    get_imports_for_session,
)
from core.cascade import get_hidden_exchange_ids
from mem0_client import search_memories


# ── Token estimator ────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """
    Rough token estimate — 1 token ≈ 4 characters.
    Good enough for budget management without a full tokenizer dependency.
    """
    return len(text) // 4


# ── Row to model ───────────────────────────────────────────────────────────────

def row_to_exchange(row) -> Exchange:
    """Convert a SQLite row to an Exchange pydantic model."""
    return Exchange(
        id=row["id"],
        session_id=row["session_id"],
        user_id=row["user_id"],
        user_turn=row["user_turn"],
        asst_turn=row["asst_turn"],
        hidden=bool(row["hidden"]),
        created_at=row["created_at"],
    )


# ── Memory filter ──────────────────────────────────────────────────────────────

def filter_memories(memories: list[str], hidden_topics: list[str]) -> list[str]:
    """
    Filter out memories that are clearly about hidden topics.
    Simple keyword check — if a hidden topic name appears in the memory
    string, exclude it from context.
    Not perfect but effective for the common case.
    """
    if not hidden_topics:
        return memories

    filtered = []
    for memory in memories:
        memory_lower = memory.lower()
        is_hidden = any(
            topic.lower() in memory_lower
            for topic in hidden_topics
        )
        if not is_hidden:
            filtered.append(memory)

    return filtered


# ── Context injection note ─────────────────────────────────────────────────────

def build_system_note(hidden_count: int, memories: list[str], hidden_topics: list[str] = None) -> str:
    """
    Build the system note prepended to context.
    Tells the model about hidden exchanges so it is not confused
    by gaps in the conversation history.
    Injects relevant memories as background knowledge.
    """
    parts = []

    if memories:
        parts.append("BACKGROUND KNOWLEDGE FROM PREVIOUS EXCHANGES:")
        for mem in memories:
            parts.append(f"  - {mem}")
        parts.append("")

    if hidden_count > 0:
        parts.append(
            f"NOTE: {hidden_count} exchange(s) have been hidden from this context "
            f"by the user. The conversation history below may have gaps — this is intentional."
        )

    if hidden_topics:
        blocked = ", ".join(hidden_topics)
        parts.append(
            f"CRITICAL INSTRUCTION: The user has explicitly BLOCKED the following topics/personas: {blocked}. "
            f"You MUST NOT mention them, and you MUST STRICTLY ABANDON any personas, accents, or roleplay "
            f"associated with those topics, even if they appear in the immediate Assistant conversation history below. "
            f"Immediately revert to a standard, helpful assistant tone."
        )

    return "\n".join(parts)


# ── Main assembler ─────────────────────────────────────────────────────────────

def assemble_context(
    session_id: str,
    user_id: str,
    current_message: str,
    api_key: str = "",
) -> ContextResponse:
    """
    Build the clean filtered context block for an API call.

    Step 1 — Load topic state and hidden exchange IDs
    Step 2 — Get visible exchanges within token budget
    Step 3 — Get relevant memories filtered against hidden topics
    Step 4 — Return assembled ContextResponse
    """

    # ── Step 1 — Topic state ───────────────────────────────────────────────────
    hidden_topics  = get_hidden_topics(session_id)
    hidden_ids     = get_hidden_exchange_ids(session_id)

    # ── Step 2 — Visible exchanges ─────────────────────────────────────────────
    all_exchanges  = get_session_exchanges(session_id, include_hidden=True)
    total_count    = len(all_exchanges)

    # Filter out hidden exchanges
    visible = [
        row_to_exchange(ex)
        for ex in all_exchanges
        if ex["id"] not in hidden_ids
    ]

    hidden_count = total_count - len(visible)

    # Apply recency limit — keep newest exchanges first, work backwards
    if len(visible) > MAX_EXCHANGES_IN_CONTEXT:
        visible = visible[-MAX_EXCHANGES_IN_CONTEXT:]

    # Apply token budget — trim oldest exchanges if over budget
    token_budget = MAX_TOKENS_CONTEXT
    final_visible = []
    for ex in reversed(visible):
        tokens = estimate_tokens(ex.user_turn + ex.asst_turn)
        if token_budget - tokens < 0:
            break
        token_budget -= tokens
        final_visible.insert(0, ex)

    # Check for imported sessions and pull their exchanges too
    imports = get_imports_for_session(session_id)
    if imports and token_budget > 500:
        for imp in imports:
            imported_exchanges = _get_imported_exchanges(
                source_session_id=imp["source_session_id"],
                import_type=imp["import_type"],
                token_budget=token_budget // len(imports),
                hidden_topics=hidden_topics,
            )
            final_visible = imported_exchanges + final_visible

    # ── Step 3 — Memories ──────────────────────────────────────────────────────
    memories = []
    if current_message.strip():
        raw_memories = search_memories(
            query=current_message,
            user_id=user_id,
            session_id=session_id,
            api_key=api_key,
        )
        memories = filter_memories(raw_memories, hidden_topics)

    # ── Step 4 — Return ────────────────────────────────────────────────────────
    return ContextResponse(
        session_id=session_id,
        exchanges=final_visible,
        memories=memories,
        hidden_count=hidden_count,
    )


# ── Imported session handler ───────────────────────────────────────────────────

def _get_imported_exchanges(
    source_session_id: str,
    import_type: str,
    token_budget: int,
    hidden_topics: list[str],
) -> list[Exchange]:
    """
    Pull exchanges from an imported session.

    full  → pull raw exchanges up to token budget
    smart → skip raw exchanges, memories handle this via mem0
            (mem0 already has the memories from the imported session,
            search_memories will surface them naturally)
    """
    if import_type == "smart":
        # Smart import is handled entirely by mem0 memory search
        # Nothing to add at the exchange level
        return []

    # Full import — pull visible exchanges from source session
    source_hidden_ids = get_hidden_exchange_ids(source_session_id)
    source_exchanges  = get_session_exchanges(source_session_id, include_hidden=True)

    visible = [
        row_to_exchange(ex)
        for ex in source_exchanges
        if ex["id"] not in source_hidden_ids
    ]

    # Apply token budget
    result = []
    remaining = token_budget
    for ex in reversed(visible):
        tokens = estimate_tokens(ex.user_turn + ex.asst_turn)
        if remaining - tokens < 0:
            break
        remaining -= tokens
        result.insert(0, ex)

    return result


# ── Context formatter ──────────────────────────────────────────────────────────

def format_for_api(context: ContextResponse) -> list[dict]:
    """
    Format the ContextResponse into the messages array format
    expected by OpenRouter / OpenAI compatible APIs.

    Returns a list of message dicts ready to be passed directly
    to the API as the messages parameter.
    """
    messages = []

    # Inject system note if we have memories or hidden exchanges
    system_note = build_system_note(context.hidden_count, context.memories, get_hidden_topics(context.session_id))
    if system_note:
        messages.append({
            "role":    "system",
            "content": system_note,
        })

    # Add visible exchanges as conversation history
    for ex in context.exchanges:
        messages.append({"role": "user",      "content": ex.user_turn})
        messages.append({"role": "assistant", "content": ex.asst_turn})

    return messages