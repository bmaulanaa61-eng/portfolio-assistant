from __future__ import annotations

import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Portfolio Assistant Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

IMPORT_ERROR = None
try:
    import json
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")

    from assistant_service import AssistantService, DEFAULT_SUGGESTIONS
    from models import ChatRequest, ChatResponse
    from security import InMemoryRateLimiter, get_client_ip, parse_allowed_origins, privacy_filter, sanitize_message

    rate_limiter = InMemoryRateLimiter()
    assistant_service = AssistantService()
except Exception as e:
    IMPORT_ERROR = traceback.format_exc()


@app.get("/")
@app.get("/health")
@app.get("/api/health")
async def health():
    if IMPORT_ERROR:
        return JSONResponse(status_code=500, content={"status": "error", "import_error": IMPORT_ERROR})
    return {
        "status": "ok",
        "service": "portfolio-assistant",
        "llm_configured": assistant_service.configured(),
    }



@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    if IMPORT_ERROR:
        raise HTTPException(status_code=500, detail=f"Startup error: {IMPORT_ERROR}")
    rate_limiter.check(get_client_ip(request))
    message = sanitize_message(payload.message)
    try:
        reply = await assistant_service.chat(message)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant backend error: {exc}") from exc

    return ChatResponse(reply=privacy_filter(reply), suggestions=DEFAULT_SUGGESTIONS, source="gemini")


async def stream_generator(message: str):
    try:
        async for chunk in assistant_service.chat_stream(message):
            data = json.dumps({"chunk": chunk})
            yield f"data: {data}\n\n"
        data = json.dumps({"done": True, "suggestions": DEFAULT_SUGGESTIONS})
        yield f"data: {data}\n\n"
    except HTTPException as exc:
        data = json.dumps({"error": exc.detail})
        yield f"data: {data}\n\n"
    except Exception as exc:
        data = json.dumps({"error": f"Assistant backend error: {exc}"})
        yield f"data: {data}\n\n"


@app.post("/api/chat/stream")
async def chat_stream_post(payload: ChatRequest, request: Request):
    if IMPORT_ERROR:
        raise HTTPException(status_code=500, detail=f"Startup error: {IMPORT_ERROR}")
    rate_limiter.check(get_client_ip(request))
    message = sanitize_message(payload.message)
    return StreamingResponse(
        stream_generator(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/chat/stream")
async def chat_stream_get(request: Request, message: str = ""):
    rate_limiter.check(get_client_ip(request))
    clean_message = sanitize_message(message)
    return StreamingResponse(
        stream_generator(clean_message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
