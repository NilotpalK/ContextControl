import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db.sqlite import init_db
from models import (
    AddExchangeRequest,
    HideTopicRequest,
    ShowTopicRequest,
    HideExchangeRequest,
    SearchRequest,
    CreateSessionRequest,
    ImportSessionRequest,
)
from db.sqlite import (
    create_session,
    get_session,
    get_user_sessions,
    get_exchange,
    get_session_exchanges,
    get_topics,
    get_topics_for_exchange,
    get_reference_target,
    save_exchange,
    save_exchange_tag,
    save_exchange_ref,
    upsert_topic,
    hide_exchange,
    show_exchange,
    touch_session,
    update_session_title,
    save_session_import,
    get_imports_for_session,
    delete_session_import,
    delete_session,
)
from core.tagger import tag_exchange
from core.cascade import on_topic_hide, on_topic_show
from core.assembler import assemble_context, format_for_api
from core.search import search
from mem0_client import add_exchange as mem0_add_exchange


# ── Startup ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup. mem0 warms lazily on first request."""
    init_db()
    print("[startup] Database initialized")

    # Warm mem0 in a background thread so the server starts instantly
    # and passes HuggingFace Spaces health checks before the timeout.
    import threading
    def _warm():
        try:
            from mem0_client import get_read_client
            get_read_client()
            print("[startup] mem0 client ready (background)")
        except Exception as e:
            print(f"[startup] mem0 pre-warm warning: {e}")
    threading.Thread(target=_warm, daemon=True).start()

    yield

app = FastAPI(
    title="ContextControl API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "ContextControl API"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Sessions ───────────────────────────────────────────────────────────────────

@app.post("/sessions")
def create_new_session(req: CreateSessionRequest):
    """Create a new isolated session for a user."""
    session_id = create_session(req.user_id, req.title)
    return {
        "session_id": session_id,
        "user_id":    req.user_id,
        "title":      req.title,
    }


@app.get("/sessions/{user_id}")
def list_sessions(user_id: str):
    """List all sessions for a user ordered by most recent."""
    sessions = get_user_sessions(user_id)
    return {
        "user_id":  user_id,
        "sessions": [dict(s) for s in sessions],
    }


@app.get("/sessions/{session_id}/detail")
def get_session_detail(session_id: str):
    """Get a single session with its imports and exchanges."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    imports = get_imports_for_session(session_id)
    exchanges = get_session_exchanges(session_id)
    return {
        "session": dict(session),
        "imports": [dict(i) for i in imports],
        "exchanges": [dict(ex) for ex in exchanges],
    }


@app.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Delete a session entirely."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"status": "success"}


@app.post("/sessions/{session_id}/import")
def import_session(session_id: str, req: ImportSessionRequest):
    """
    Import exchanges or memories from another session into this one.
    full  → imports raw exchanges
    smart → imports via mem0 memories only (lighter)
    """
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Target session not found")
    if not get_session(req.source_session_id):
        raise HTTPException(status_code=404, detail="Source session not found")

    import_id = save_session_import(
        target_session_id=session_id,
        source_session_id=req.source_session_id,
        import_type=req.import_type,
    )
    return {
        "import_id":         import_id,
        "target_session_id": session_id,
        "source_session_id": req.source_session_id,
        "import_type":       req.import_type,
    }


@app.delete("/sessions/{session_id}/import/{source_id}")
def remove_import(session_id: str, source_id: str):
    """Remove a session import."""
    delete_session_import(session_id, source_id)
    return {"status": "removed"}


# ── Exchanges ──────────────────────────────────────────────────────────────────

@app.post("/exchange")
async def add_exchange(req: AddExchangeRequest, bg_tasks: BackgroundTasks):
    """
    Store a new exchange. This is the main write endpoint.
    Pipeline:
      1. Save raw exchange pair to SQLite
      2. Run tagger AND mem0 ingest concurrently (both are blocking Ollama calls)
      3. Save topic tags and chain refs to SQLite
      4. Upsert topic node
    """
    if not get_session(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Step 1 — Save raw exchange
    exchange_id = save_exchange(
        session_id=req.session_id,
        user_id=req.user_id,
        user_turn=req.user_turn,
        asst_turn=req.asst_turn,
    )

    # Steps 2+5 — Run tagger AND mem0 ingest in parallel
    def _tag():
        return tag_exchange(
            user_turn=req.user_turn,
            asst_turn=req.asst_turn,
            session_id=req.session_id,
            exchange_id=exchange_id,
        )

    def _mem0():
        try:
            mem0_add_exchange(
                user_turn=req.user_turn,
                asst_turn=req.asst_turn,
                session_id=req.session_id,
                user_id=req.user_id,
            )
        except Exception as e:
            print(f"[mem0] Warning: {e}")

    # Await the incredibly fast OpenRouter tagger (ensuring cascade tags are ready instantly)
    tag = await asyncio.to_thread(_tag)
    
    # Push the slow local mem0 graph ingestion to the background
    bg_tasks.add_task(_mem0)

    # Step 3 — Save topic tags
    if not tag.is_passing_mention:
        save_exchange_tag(
            exchange_id=exchange_id,
            topic_name=tag.primary_topic,
            is_primary=True,
            is_mention_only=False,
        )

        for mention in tag.mentions:
            save_exchange_tag(
                exchange_id=exchange_id,
                topic_name=mention,
                is_primary=False,
                is_mention_only=True,
            )

        if tag.references_exchange_id:
            save_exchange_ref(
                from_id=exchange_id,
                to_id=tag.references_exchange_id,
                ref_type=tag.reference_type or "direct",
            )

        # Step 4 — Upsert topic node
        upsert_topic(
            name=tag.primary_topic,
            session_id=req.session_id,
            user_id=req.user_id,
            parent=tag.parent_topic,
        )

    # Auto-generate session title from first exchange
    session = get_session(req.session_id)
    if session and session["exchange_count"] == 1:
        title = req.user_turn[:60] + ("..." if len(req.user_turn) > 60 else "")
        update_session_title(req.session_id, title)

    touch_session(req.session_id)

    return {
        "exchange_id":   exchange_id,
        "tag":           tag.model_dump(),
        "session_id":    req.session_id,
    }


@app.get("/exchange/{exchange_id}")
def get_exchange_detail(exchange_id: str):
    """Get a single exchange with its topic tags and chain reference."""
    row = get_exchange(exchange_id)
    if not row:
        raise HTTPException(status_code=404, detail="Exchange not found")

    topics    = get_topics_for_exchange(exchange_id)
    ref_target = get_reference_target(exchange_id)

    return {
        "exchange":   dict(row),
        "topics":     topics,
        "references": ref_target,
    }


@app.post("/exchange/hide")
def hide_single_exchange(req: HideExchangeRequest):
    """Hide a single exchange."""
    row = get_exchange(req.exchange_id)
    if not row:
        raise HTTPException(status_code=404, detail="Exchange not found")

    hide_exchange(req.exchange_id)
    return {
        "exchange_id": req.exchange_id,
        "status":      "hidden",
    }


@app.post("/exchange/show")
def show_single_exchange(req: HideExchangeRequest):
    """Show (unhide) a single exchange."""
    row = get_exchange(req.exchange_id)
    if not row:
        raise HTTPException(status_code=404, detail="Exchange not found")

    show_exchange(req.exchange_id)
    return {
        "exchange_id": req.exchange_id,
        "status":      "visible",
    }


# ── Topics ─────────────────────────────────────────────────────────────────────

@app.get("/topics/{session_id}")
def list_topics(session_id: str):
    """List all topics for a session with status and exchange counts."""
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    topics = get_topics(session_id)
    return {
        "session_id": session_id,
        "topics":     [dict(t) for t in topics],
    }


@app.post("/topic/hide")
def hide_topic(req: HideTopicRequest):
    """
    Hide a topic and run cascade.
    Returns all affected exchange IDs including cascade-hidden ones.
    """
    if not get_session(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    affected = on_topic_hide(req.topic_name, req.session_id)
    return {
        "topic_name":   req.topic_name,
        "status":       "hidden",
        "affected_exchanges": affected,
        "total_hidden": len(affected),
    }


@app.post("/topic/show")
def show_topic(req: ShowTopicRequest):
    """
    Unhide a topic.
    Returns newly visible exchanges and any stale exchange IDs.
    """
    if not get_session(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    result = on_topic_show(req.topic_name, req.session_id)
    return {
        "topic_name":    req.topic_name,
        "status":        "active",
        "newly_visible": result["newly_visible"],
        "stale":         result["stale"],
    }


# ── Context ────────────────────────────────────────────────────────────────────

@app.get("/context/{session_id}")
def get_context(session_id: str, user_id: str, current_message: str):
    """
    Build and return the filtered context block for the next API call.
    This is what you call before sending a message to OpenRouter.
    Returns exchanges, memories, and hidden count.
    Also returns the messages array formatted for the OpenRouter API.
    """
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    context = assemble_context(
        session_id=session_id,
        user_id=user_id,
        current_message=current_message,
    )

    # Also format for direct API use
    formatted = format_for_api(context)

    return {
        "session_id":   session_id,
        "exchanges":    [ex.model_dump() for ex in context.exchanges],
        "memories":     context.memories,
        "hidden_count": context.hidden_count,
        "formatted_messages": formatted,
    }

# ── Chat ───────────────────────────────────────────────────────────────────────

from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MAIN_MODEL
from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id:      str
    user_id:         str
    message:         str
    system_prompt:   str = "You are a helpful assistant."


@app.post("/chat")
async def chat(req: ChatRequest, request: Request, background_tasks: BackgroundTasks):
    """
    All-in-one chat endpoint for testing.
    """
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing OpenRouter API Key in headers")

    if not api_key.startswith("sk-or-v1-"):
        raise HTTPException(status_code=401, detail="Invalid API Key format. OpenRouter keys must start with 'sk-or-v1-'")

    if not get_session(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Step 1 — Assemble filtered context
    context    = assemble_context(
        session_id=req.session_id,
        user_id=req.user_id,
        current_message=req.message,
        api_key=api_key,
    )
    messages   = format_for_api(context)

    # Prepend system prompt
    messages   = [{"role": "system", "content": req.system_prompt}] + messages

    # Append current user message
    messages.append({"role": "user", "content": req.message})

    # We need to capture the full assistant reply to save it later
    full_reply = []

    # Step 2 — Call OpenRouter with streaming
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )

    def _background_pipeline(assistant_reply: str):
        print(f"[chat] Background pipeline started for {req.session_id}")
        
        # 1. Store exchange
        exchange_id = save_exchange(
            session_id=req.session_id,
            user_id=req.user_id,
            user_turn=req.message,
            asst_turn=assistant_reply,
        )

        # 2. Run tagger and mem0
        tag = tag_exchange(
            user_turn=req.message,
            asst_turn=assistant_reply,
            session_id=req.session_id,
            exchange_id=exchange_id,
            api_key=api_key,
        )

        try:
            mem0_add_exchange(
                user_turn=req.message,
                asst_turn=assistant_reply,
                session_id=req.session_id,
                user_id=req.user_id,
                api_key=api_key,
            )
        except Exception as e:
            print(f"[mem0] Warning: {e}")

        # 3. Save tags and nodes
        if not tag.is_passing_mention:
            save_exchange_tag(
                exchange_id=exchange_id,
                topic_name=tag.primary_topic,
                is_primary=True,
                is_mention_only=False,
            )
            for mention in tag.mentions:
                save_exchange_tag(
                    exchange_id=exchange_id,
                    topic_name=mention,
                    is_primary=False,
                    is_mention_only=True,
                )
            if tag.references_exchange_id:
                save_exchange_ref(
                    from_id=exchange_id,
                    to_id=tag.references_exchange_id,
                    ref_type=tag.reference_type or "direct",
                )
            upsert_topic(
                name=tag.primary_topic,
                session_id=req.session_id,
                user_id=req.user_id,
                parent=tag.parent_topic,
            )

        # 4. Auto title session on first message
        session = get_session(req.session_id)
        if session and session["exchange_count"] == 1:
            title = req.message[:60] + ("..." if len(req.message) > 60 else "")
            update_session_title(req.session_id, title)

        touch_session(req.session_id)
        print(f"[chat] Background pipeline finished for {req.session_id}")

    async def stream_generator():
        try:
            stream = client.chat.completions.create(
                model=MAIN_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if getattr(delta, "content", None) is not None:
                        content = delta.content
                        full_reply.append(content)
                        yield content
                    
            # Queue background task after stream completes
            final_text = "".join(full_reply)
            background_tasks.add_task(_background_pipeline, final_text)
            
        except Exception as e:
            yield f"\n\n[Error: {e}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")


# ── Search ─────────────────────────────────────────────────────────────────────

@app.get("/search")
def search_exchanges(session_id: str, user_id: str, query: str):
    """
    Search topics and exchanges.
    Tries exact topic match first, falls back to semantic search.
    Returns matching exchanges with topic tags and warning flags.
    """
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    results = search(
        query=query,
        session_id=session_id,
        user_id=user_id,
    )

    return {
        "query":   query,
        "count":   len(results),
        "results": [r.model_dump() for r in results],
    }