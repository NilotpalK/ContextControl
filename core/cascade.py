from db.sqlite import (
    get_session_exchanges,
    get_topics_for_exchange,
    get_primary_topics_for_exchange,
    get_hidden_topics,
    get_active_topics,
    get_exchanges_referencing,
    get_reference_target,
    set_topic_status,
    hide_exchange,
    show_exchange,
    get_exchanges_for_topic,
    get_matched_topic_names,
)


# ── Core filtering rule ────────────────────────────────────────────────────────

def should_hide_exchange(exchange_id: str, hidden_topics: list[str]) -> bool:
    """
    Core rule: hide an exchange if ALL of its PRIMARY topic connections are hidden.
    Mention-only tags (e.g. bare 'Postgres', 'index') are excluded — they are
    side-references, not the main topic, and should not prevent hiding.
    An exchange with no primary tags is kept visible.
    """
    topics = get_primary_topics_for_exchange(exchange_id)

    # Exchange has no primary topics yet (tagger may not have run) — keep it
    if not topics:
        return False

    # If every primary topic this exchange is connected to is hidden → hide it
    return all(t in hidden_topics for t in topics)


# ── Cascade check ──────────────────────────────────────────────────────────────

def cascade_check(exchange_id: str, hidden_exchange_ids: set[str]) -> set[str]:
    """
    Depth-first traversal forward through reference edges.
    If exchange A references hidden exchange B, A gets cascade hidden.
    If exchange C references A, C gets cascade hidden too.
    Walks the full chain until no more downstream references are found.
    Returns set of all exchange IDs caught in the cascade.
    """
    cascade_hidden = set()
    to_check       = [exchange_id]
    visited        = set()

    while to_check:
        current = to_check.pop()
        if current in visited:
            continue
        visited.add(current)

        # Find all exchanges that reference this one
        referencing = get_exchanges_referencing(current)
        for ref_id in referencing:
            if ref_id not in hidden_exchange_ids and ref_id not in cascade_hidden:
                cascade_hidden.add(ref_id)
                to_check.append(ref_id)

    return cascade_hidden


# ── Main assembler-facing function ─────────────────────────────────────────────

def get_hidden_exchange_ids(session_id: str) -> set[str]:
    """
    Called by the assembler before every API call.
    Returns the complete set of exchange IDs to exclude from context.

    Two passes:
      Pass 1 — direct hide: exchanges where all topic connections are hidden
      Pass 2 — cascade hide: exchanges that reference something from pass 1
    """
    hidden_topics   = get_hidden_topics(session_id)
    all_exchanges   = get_session_exchanges(session_id, include_hidden=True)
    hidden_ids      = set()

    # Pass 1 — direct topic filtering
    for ex in all_exchanges:
        if should_hide_exchange(ex["id"], hidden_topics):
            hidden_ids.add(ex["id"])

    # Pass 2 — cascade through reference edges
    cascade_ids = set()
    for exchange_id in hidden_ids:
        cascade_ids.update(cascade_check(exchange_id, hidden_ids))

    # Merge both passes
    hidden_ids.update(cascade_ids)
    return hidden_ids


# ── Topic hide ─────────────────────────────────────────────────────────────────

def on_topic_hide(topic_name: str, session_id: str) -> list[str]:
    """
    Called when user hides a topic via the API.
    1. Flips topic status to hidden in SQLite
    2. Computes which exchanges are now hidden (direct + cascade)
    3. Returns list of affected exchange IDs for the API response
       so the UI can show the user exactly what changed
    """
    # Flip topic status
    set_topic_status(topic_name, session_id, "hidden")

    # Recompute full hidden set with updated topic state
    hidden_ids = get_hidden_exchange_ids(session_id)

    # Update hidden flag on all affected exchanges in SQLite
    all_exchanges = get_session_exchanges(session_id, include_hidden=True)
    for ex in all_exchanges:
        if ex["id"] in hidden_ids:
            hide_exchange(ex["id"])
        else:
            show_exchange(ex["id"])

    return list(hidden_ids)


# ── Topic show ─────────────────────────────────────────────────────────────────

def on_topic_show(topic_name: str, session_id: str) -> dict:
    """
    Called when user shows (unhides) a topic via the API.
    1. Flips topic status back to active
    2. Recomputes hidden set — some exchanges will now become visible
    3. Detects stale exchanges — ones answered while topic was hidden
       that may now be inconsistent
    4. Returns affected exchange IDs and stale exchange IDs
    """
    # Flip topic status
    set_topic_status(topic_name, session_id, "active")

    # Recompute hidden set with updated state
    hidden_ids    = get_hidden_exchange_ids(session_id)
    all_exchanges = get_session_exchanges(session_id, include_hidden=True)

    newly_visible = []
    for ex in all_exchanges:
        if ex["id"] in hidden_ids:
            hide_exchange(ex["id"])
        else:
            show_exchange(ex["id"])
            newly_visible.append(ex["id"])

    # Detect stale exchanges — visible exchanges that reference
    # exchanges connected to the topic that was just unhidden
    # These may have been answered with incomplete context
    stale_ids = _detect_stale_exchanges(topic_name, session_id, newly_visible)

    return {
        "newly_visible": newly_visible,
        "stale":         stale_ids,
    }


# ── Stale detection ────────────────────────────────────────────────────────────

def _detect_stale_exchanges(
    topic_name: str,
    session_id: str,
    visible_exchange_ids: list[str]
) -> list[str]:
    """
    Find exchanges that were answered while the topic was hidden.
    topic_name may be a partial name (e.g. 'Postgres') — we resolve
    all matching topic nodes and collect their exchange IDs.
    """
    matched_names = get_matched_topic_names(topic_name, session_id)

    topic_exchanges: set[str] = set()
    for name in matched_names:
        for ex in get_exchanges_for_topic(name, session_id):
            topic_exchanges.add(ex["id"])

    stale = []
    for exchange_id in visible_exchange_ids:
        ref_target = get_reference_target(exchange_id)
        if ref_target and ref_target in topic_exchanges:
            stale.append(exchange_id)

    return stale