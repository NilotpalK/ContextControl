from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Database models ────────────────────────────────────────────────────────────

class Exchange(BaseModel):
    id:         str
    session_id: str
    user_id:    str
    user_turn:  str
    asst_turn:  str
    hidden:     bool = False
    created_at: Optional[datetime] = None


class Topic(BaseModel):
    name:           str
    session_id:     str
    user_id:        str
    parent:         Optional[str] = None
    status:         str = "active"   # "active" or "hidden"
    exchange_count: int = 0


class Session(BaseModel):
    id:             str
    user_id:        str
    title:          Optional[str] = None
    created_at:     Optional[datetime] = None
    last_active:    Optional[datetime] = None
    exchange_count: int = 0


class TagResult(BaseModel):
    primary_topic:          str
    parent_topic:           Optional[str] = None
    is_new_topic:           bool = True
    mentions:               list[str] = []
    references_exchange_id: Optional[str] = None
    reference_type:         Optional[str] = None   # "direct" or "implicit"
    is_passing_mention:     bool = False
    confidence:             float = 0.0


# ── API request models ─────────────────────────────────────────────────────────

class AddExchangeRequest(BaseModel):
    session_id: str
    user_id:    str
    user_turn:  str
    asst_turn:  str


class HideTopicRequest(BaseModel):
    session_id: str
    topic_name: str


class ShowTopicRequest(BaseModel):
    session_id: str
    topic_name: str


class HideExchangeRequest(BaseModel):
    exchange_id: str


class SearchRequest(BaseModel):
    session_id: str
    user_id:    str
    query:      str


class CreateSessionRequest(BaseModel):
    user_id: str
    title:   Optional[str] = None


class ImportSessionRequest(BaseModel):
    source_session_id: str
    import_type:       str = "smart"   # "full" or "smart"


# ── API response models ────────────────────────────────────────────────────────

class ContextResponse(BaseModel):
    session_id:   str
    exchanges:    list[Exchange]
    memories:     list[str]
    hidden_count: int


class HideTopicResponse(BaseModel):
    topic_name:        str
    cascade_hidden:    list[str]   # exchange IDs hidden by cascade
    total_hidden:      int


class SearchResult(BaseModel):
    exchange:     Exchange
    topics:       list[str]
    has_warning:  bool = False     # True if exchange references hidden context
    match_type:   str = "exact"    # "exact" or "fuzzy"


class SanitizeResult(BaseModel):
    clean_text:   str
    was_modified: bool
    detections:   list[str] = []