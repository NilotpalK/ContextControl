from mem0 import Memory
from config import MEM0_CONFIG

# ── Client singleton ───────────────────────────────────────────────────────────
# Initialized once and reused. mem0 loads models and connects to
# Chroma + Kuzu on first call — we don't want that happening on every request.

_client: Memory | None = None


def get_client() -> Memory:
    global _client
    if _client is None:
        _client = Memory.from_config(MEM0_CONFIG)
    return _client


# ── Public functions ───────────────────────────────────────────────────────────

def add_exchange(user_turn: str, asst_turn: str, session_id: str, user_id: str):
    """
    Feed a completed exchange to mem0.
    mem0 extracts facts from both turns and stores them in:
      - Chroma (vector store) for semantic retrieval
      - Kuzu (graph store) for entity relationships
    Both writes happen atomically inside mem0's add() call.
    """
    messages = [
        {"role": "user",      "content": user_turn},
        {"role": "assistant", "content": asst_turn},
    ]
    get_client().add(
        messages=messages,
        user_id=user_id,
        run_id=session_id,     # run_id scopes memories to this session
    )


def search_memories(query: str, user_id: str, session_id: str, limit: int = 5) -> list[str]:
    """
    Retrieve semantically relevant memories for the current user message.
    Returns a flat list of memory strings ready to be injected into context.
    Scoped to this session via run_id so memories from other sessions
    don't bleed in — matching our session isolation design decision.
    """
    results = get_client().search(
        query=query,
        user_id=user_id,
        run_id=session_id,
        limit=limit,
    )

    # mem0 returns a dict with a 'results' key containing memory objects
    memories = []
    for item in results.get("results", []):
        memory_text = item.get("memory", "")
        if memory_text:
            memories.append(memory_text)

    return memories


def delete_session_memories(session_id: str, user_id: str):
    """
    Delete all memories for a session.
    Not used in v1 but wired up for when permanent deletion comes in v2.
    """
    get_client().delete_all(user_id=user_id, run_id=session_id)