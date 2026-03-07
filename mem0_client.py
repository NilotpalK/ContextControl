from mem0 import Memory
from config import MEM0_CONFIG

# ── Client singleton ───────────────────────────────────────────────────────────
# Initialized per API key to cleanly silo API credentials in memory.

import copy
_write_clients: dict[str, Memory] = {}
_read_client: Memory | None = None

def get_read_client() -> Memory:
    """Singleton strictly for synchronous search. Never blocked by dynamic API key generation."""
    global _read_client
    if _read_client is None:
        cfg = copy.deepcopy(MEM0_CONFIG)
        cfg["llm"]["config"]["api_key"] = "read_only_dummy"
        _read_client = Memory.from_config(cfg)
    return _read_client

def get_write_client(api_key: str) -> Memory:
    """Siloed instantiation for background entity extraction using real dynamic LLM credentials."""
    if not api_key:
        api_key = "dummy_key"
    if api_key not in _write_clients:
        cfg = copy.deepcopy(MEM0_CONFIG)
        cfg["llm"]["config"]["api_key"] = api_key
        _write_clients[api_key] = Memory.from_config(cfg)
    return _write_clients[api_key]


# ── Public functions ───────────────────────────────────────────────────────────

def add_exchange(user_turn: str, asst_turn: str, session_id: str, user_id: str, api_key: str):
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
    get_write_client(api_key).add(
        messages=messages,
        user_id=user_id,
        run_id=session_id,     # run_id scopes memories to this session
    )


def search_memories(query: str, user_id: str, session_id: str, api_key: str, limit: int = 5) -> list[str]:
    """
    Retrieve semantically relevant memories for the current user message.
    Returns a flat list of memory strings ready to be injected into context.
    Scoped to this session via run_id so memories from other sessions
    don't bleed in — matching our session isolation design decision.
    """
    results = get_read_client().search(
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