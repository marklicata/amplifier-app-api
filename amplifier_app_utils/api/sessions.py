"""Session management API endpoints."""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..core import SessionManager
from ..models import (
    MessageRequest,
    MessageResponse,
    SessionCreateRequest,
    SessionInfo,
    SessionListResponse,
    SessionResponse,
)
from ..storage import Database, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def get_session_manager(db: Database = Depends(get_db)) -> SessionManager:
    """Dependency to get session manager."""
    return SessionManager(db)


@router.post("/create", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Create a new session."""
    try:
        session = await manager.create_session(
            bundle=request.bundle,
            provider=request.provider,
            model=request.model,
            config=request.config,
            metadata=request.metadata,
        )

        return SessionResponse(
            session_id=session.session_id,
            status=session.status,
            metadata=session.metadata.model_dump(),
            message="Session created successfully",
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionListResponse:
    """List all sessions."""
    try:
        sessions = await manager.list_sessions(limit=limit, offset=offset)

        session_infos = [
            SessionInfo(
                session_id=s.session_id,
                status=s.status,
                bundle=s.metadata.bundle,
                provider=s.metadata.provider,
                message_count=s.metadata.message_count,
                created_at=s.metadata.created_at,
                updated_at=s.metadata.updated_at,
            )
            for s in sessions
        ]

        return SessionListResponse(sessions=session_infos, total=len(session_infos))
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Get session details."""
    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        metadata=session.metadata.model_dump(),
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Delete a session."""
    success = await manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted successfully"}


@router.post("/{session_id}/resume", response_model=SessionResponse)
async def resume_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Resume an existing session."""
    session = await manager.resume_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        metadata=session.metadata.model_dump(),
        message="Session resumed successfully",
    )


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: str,
    request: MessageRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> MessageResponse:
    """Send a message to a session."""
    try:
        response = await manager.send_message(
            session_id=session_id,
            message=request.message,
            context=request.context,
        )

        return MessageResponse(
            session_id=response["session_id"],
            response=response["response"],
            metadata=response["metadata"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request: MessageRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    """Send a message and stream the response using Server-Sent Events (SSE)."""
    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        """Generate SSE events from amplifier-core streaming."""
        try:
            # Send connection acknowledgment
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Stream the response from amplifier
            async for event in manager.stream_message(session_id, request.message, request.context):
                event_data = json.dumps(event)
                yield f"data: {event_data}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run

            # Send completion event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            error_event = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Cancel current operation in a session."""
    amplifier_session = await manager.get_amplifier_session(session_id)
    if not amplifier_session:
        raise HTTPException(status_code=404, detail="Session not found or not active")

    try:
        # Request cancellation through amplifier-core
        if hasattr(amplifier_session, "status") and hasattr(
            amplifier_session.status, "cancellation_token"
        ):
            amplifier_session.status.cancellation_token.request_cancel()
            return {"message": "Cancellation requested"}
        else:
            return {"message": "Session does not support cancellation"}

    except Exception as e:
        logger.error(f"Error cancelling session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
