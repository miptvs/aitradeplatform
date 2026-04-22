from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.events.service import event_stream

router = APIRouter()


@router.get("/events")
async def events() -> StreamingResponse:
    return StreamingResponse(event_stream(), media_type="text/event-stream")
