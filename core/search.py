from db.sqlite import (
    get_topics,
    get_exchanges_for_topic,
    get_topics_for_exchange,
    get_reference_target,
    get_hidden_topics,
)
from mem0_client import search_memories
from models import Exchange, SearchResult


# ── Row converter ──────────────────────────────────────────────────────────────

def row_to_exchange(row) -> Exchange:
    return Exchange(
        id=row["id"],
        session_id=row["session_id"],
        user_id=row["user_id"],
        user_turn=row["user_turn"],
        asst_turn=row["asst_turn"],
        hidden=bool(row["hidden"]),
        created_at=row["created_at"],
    )


# ── Warning checker ────────────────────────────────────────────────────────────

def has_hidden_reference(exchange_id: str, hidden_topics: list[str]) -> bool:
    """
    Check if this exchange references an exchange connected to a hidden topic.
    Used to show a warning flag in search results so the user knows
    this exchange has a broken or polluted reference.
    """
    ref_target = get_reference_target(exchange_id)
    if not ref_target:
        return False

    ref_topics = get_topics_for_exchange(ref_target)
    return any(t in hidden_topics for t in ref_topics)


# ── Exact search ───────────────────────────────────────────────────────────────

def exact_search(
    query: str,
    session_id: str,
    user_id: str,
) -> list[SearchResult]:
    """
    Match query directly against topic names in SQLite.
    Case insensitive. Partial match supported — 'mongo' matches 'MongoDB'.
    Returns all exchanges tagged with any matching topic.
    """
    all_topics   = get_topics(session_id)
    hidden_topics = get_hidden_topics(session_id)
    query_lower  = query.lower()

    # Find matching topic nodes
    matched_topics = [
        t["name"] for t in all_topics
        if query_lower in t["name"].lower()
    ]

    if not matched_topics:
        return []

    # Collect all exchanges for matched topics, deduplicate
    seen         = set()
    results      = []

    for topic_name in matched_topics:
        exchanges = get_exchanges_for_topic(topic_name, session_id)
        for row in exchanges:
            if row["id"] in seen:
                continue
            seen.add(row["id"])

            exchange = row_to_exchange(row)
            topics   = get_topics_for_exchange(row["id"])
            warning  = has_hidden_reference(row["id"], hidden_topics)

            results.append(SearchResult(
                exchange=exchange,
                topics=topics,
                has_warning=warning,
                match_type="exact",
            ))

    return results


# ── Fuzzy search ───────────────────────────────────────────────────────────────

def fuzzy_search(
    query: str,
    session_id: str,
    user_id: str,
) -> list[SearchResult]:
    """
    Semantic search via mem0 when exact topic match fails.
    Handles natural language queries like 'database stuff' or
    'that conversation about hooks'.
    Returns exchanges ranked by semantic relevance.
    """
    hidden_topics = get_hidden_topics(session_id)

    # Use mem0 semantic search with higher limit for search use case
    memories = search_memories(
        query=query,
        user_id=user_id,
        session_id=session_id,
        limit=10,
    )

    if not memories:
        return []

    # mem0 returns memory strings — we need to find which exchanges
    # these memories came from by matching content
    from db.sqlite import get_session_exchanges
    all_exchanges = get_session_exchanges(session_id, include_hidden=True)

    results  = []
    seen     = set()

    for memory in memories:
        memory_lower = memory.lower()
        for row in all_exchanges:
            if row["id"] in seen:
                continue

            # Match memory content against exchange content
            if (
                memory_lower in row["user_turn"].lower() or
                memory_lower in row["asst_turn"].lower() or
                any(word in row["user_turn"].lower() for word in memory_lower.split() if len(word) > 4)
            ):
                seen.add(row["id"])
                exchange = row_to_exchange(row)
                topics   = get_topics_for_exchange(row["id"])
                warning  = has_hidden_reference(row["id"], hidden_topics)

                results.append(SearchResult(
                    exchange=exchange,
                    topics=topics,
                    has_warning=warning,
                    match_type="fuzzy",
                ))

    return results


# ── Public entry point ─────────────────────────────────────────────────────────

def search(
    query: str,
    session_id: str,
    user_id: str,
) -> list[SearchResult]:
    """
    Main search function. Always call this — never call exact or fuzzy directly.

    Tries exact match first.
    Falls back to fuzzy if exact returns nothing.
    Always returns the same SearchResult shape regardless of path taken.
    """
    results = exact_search(query, session_id, user_id)

    if not results:
        print(f"[search] No exact match for '{query}' — trying fuzzy")
        results = fuzzy_search(query, session_id, user_id)

    return results  