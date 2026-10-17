"""Phase 6 — Direct messaging.

Sending is a normal REST POST (so it's easy to test, retry, and reason
about); delivery to the *other* participant(s) is pushed over a WebSocket
when they're online, per the build plan: "(Optional) WebSocket endpoint for
real-time delivery -- FastAPI has native support." The socket is push-only
(server -> client); the client never sends chat content over it.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import tuple_
from sqlalchemy.orm import Session

from .. import models, oauth2, schemas
from ..database import get_db
from ..pagination import decode_cursor, encode_cursor
from ..ws_manager import manager

router = APIRouter(tags=["Messages"], responses={404: {"description": "Not found"}})


def _get_conversation_or_404(db: Session, conversation_id: int) -> models.Conversations:
    conversation = db.query(models.Conversations).filter(models.Conversations.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Conversation with id {conversation_id} not found")
    return conversation


def _require_participant(db: Session, conversation_id: int, user_id: int) -> None:
    is_participant = (
        db.query(models.ConversationParticipants)
        .filter(
            models.ConversationParticipants.conversation_id == conversation_id,
            models.ConversationParticipants.user_id == user_id,
        )
        .first()
    )
    if not is_participant:
        # 404, not 403: confirming a conversation *exists* to someone who
        # isn't part of it leaks its existence. Same "don't confirm what
        # you can't see" instinct as the ownership checks in posts.py.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


def _participant_ids(db: Session, conversation_id: int) -> list[int]:
    rows = (
        db.query(models.ConversationParticipants.user_id)
        .filter(models.ConversationParticipants.conversation_id == conversation_id)
        .all()
    )
    return [row[0] for row in rows]


def _to_conversation_response(db: Session, conversation: models.Conversations) -> schemas.ConversationResponse:
    rows = (
        db.query(models.Users.id, models.Users.email)
        .join(models.ConversationParticipants, models.ConversationParticipants.user_id == models.Users.id)
        .filter(models.ConversationParticipants.conversation_id == conversation.id)
        .all()
    )
    participants = [schemas.ConversationParticipantOut(user_id=uid, email=email) for uid, email in rows]
    return schemas.ConversationResponse(id=conversation.id, created_at=conversation.created_at, participants=participants)


# --- REST: conversations -----------------------------------------------------

@router.post("/conversations", response_model=schemas.ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: schemas.ConversationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    # Participants join table (not a flat sender/recipient pair) -- see the
    # Phase 6 gotcha/model docstring: this is what lets a "conversation"
    # scale from a 1:1 DM to a group chat later with zero schema changes.
    participant_ids = set(payload.participant_ids) | {current_user.id}
    if len(participant_ids) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A conversation needs at least one other participant")

    found = db.query(models.Users.id).filter(models.Users.id.in_(participant_ids)).all()
    if len(found) != len(participant_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more participant_ids do not exist")

    new_conversation = models.Conversations()
    db.add(new_conversation)
    db.flush()  # assigns new_conversation.id without committing yet, so the participant rows below can reference it

    for user_id in participant_ids:
        db.add(models.ConversationParticipants(conversation_id=new_conversation.id, user_id=user_id))
    db.commit()
    db.refresh(new_conversation)

    return _to_conversation_response(db, new_conversation)


@router.get("/conversations", response_model=list[schemas.ConversationResponse], status_code=status.HTTP_200_OK)
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    conversation_ids = [
        row[0]
        for row in db.query(models.ConversationParticipants.conversation_id)
        .filter(models.ConversationParticipants.user_id == current_user.id)
        .all()
    ]
    conversations = (
        db.query(models.Conversations)
        .filter(models.Conversations.id.in_(conversation_ids))
        .order_by(models.Conversations.created_at.desc())
        .limit(limit)
        .offset(skip)
        .all()
    )
    return [_to_conversation_response(db, c) for c in conversations]


# --- REST: messages -----------------------------------------------------------

@router.get("/conversations/{id}/messages", response_model=schemas.MessagePage, status_code=status.HTTP_200_OK)
def get_messages(
    id: int,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    _get_conversation_or_404(db, id)
    _require_participant(db, id, current_user.id)

    # Same cursor-pagination pattern as the feed (Phase 3) -- see
    # pagination.py. We fetch newest-first (most recent page = the messages
    # you'd see first opening a chat), then reverse just the returned page so
    # it renders top-to-bottom in chronological order.
    query = db.query(models.Messages).filter(models.Messages.conversation_id == id)
    if cursor:
        parts = decode_cursor(cursor)
        cursor_created_at, cursor_id = datetime.fromisoformat(parts[0]), int(parts[1])
        query = query.filter(tuple_(models.Messages.created_at, models.Messages.id) < (cursor_created_at, cursor_id))

    rows = query.order_by(models.Messages.created_at.desc(), models.Messages.id.desc()).limit(limit).all()

    next_cursor = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at.isoformat(), last.id)

    return schemas.MessagePage(items=list(reversed(rows)), next_cursor=next_cursor)


@router.post("/conversations/{id}/messages", response_model=schemas.MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    id: int,
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    _get_conversation_or_404(db, id)
    _require_participant(db, id, current_user.id)

    new_message = models.Messages(conversation_id=id, sender_id=current_user.id, content=payload.content)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    # Real-time push to every OTHER participant who's currently connected.
    # The sender already has the message as this request's response, so we
    # don't echo it back down their own socket too.
    message_out = schemas.MessageResponse.model_validate(new_message)
    ws_payload = schemas.WSMessageOut(message=message_out).model_dump(mode="json")
    for participant_id in _participant_ids(db, id):
        if participant_id != current_user.id:
            await manager.send_to_user(participant_id, ws_payload)

    return new_message


@router.patch("/conversations/{id}/read", status_code=status.HTTP_200_OK)
def mark_conversation_read(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    _get_conversation_or_404(db, id)
    _require_participant(db, id, current_user.id)

    updated = (
        db.query(models.Messages)
        .filter(
            models.Messages.conversation_id == id,
            models.Messages.sender_id != current_user.id,
            models.Messages.is_read.is_(False),
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return {"marked_read": updated}


# --- WebSocket: real-time delivery --------------------------------------------

@router.websocket("/ws/messages")
async def messages_websocket(websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)):
    """Connect with: ws://host/ws/messages?token=<access_token>

    A WS handshake is still just one HTTP request under the hood, so FastAPI
    dependencies (`db`) work the normal way -- but a browser WebSocket client
    can't attach a custom Authorization header the way it can on a fetch()
    call, so the access token travels as a query parameter instead. (Query
    strings can end up in server access logs -- the docx's "WebSocket auth"
    section covers the tradeoffs and an alternative: authenticate, then
    upgrade.)
    """
    try:
        current_user = oauth2.get_current_user_from_token(token, db)
    except HTTPException:
        # Reject *before* accept() so the client gets a clean handshake
        # failure instead of a socket that opens and then immediately dies.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(current_user.id, websocket)
    try:
        while True:
            # This socket is push-only from the server's side, but we still
            # need to `await` something so Starlette can detect the client
            # disconnecting (closing the tab, losing network, ...) and raise
            # WebSocketDisconnect below. Any inbound text is currently
            # ignored -- see docx for turning this into a two-way channel
            # (e.g. typing indicators).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(current_user.id, websocket)
