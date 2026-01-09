"""
로컬 AI 서버 (quiz22.html용)
- 브라우저(HTML)에서 http://127.0.0.1:8787 로 접속
- API 키는 브라우저에 넣지 않고, 이 서버의 환경변수로만 관리

실행:
  pip install fastapi uvicorn openai
  (PowerShell) $env:OPENAI_API_KEY="YOUR_KEY"
  python ai_server.py

테스트:
  http://127.0.0.1:8787/health
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import json
import time
from pydantic import BaseModel

try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None  # type: ignore


"""Render 배포/로컬 실행 공용 설정

- Render에서는 외부에서 접근 가능하도록 host=0.0.0.0 로 바인딩해야 하고,
  포트는 Render가 주는 환경변수 PORT 를 사용해야 합니다.
- 로컬에서는 PORT가 없으므로 기본값 8787로 동작합니다.
"""

APP_HOST = "0.0.0.0"
APP_PORT = int(os.environ.get("PORT", "8787"))
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2")  # 필요시 환경변수로 변경

API_KEY = os.getenv("OPENAI_API_KEY")
# 개발 편의: 키가 없으면 서버를 즉시 실패시켜(=원인 명확) "400" 대신 콘솔에서 바로 확인할 수 있게 함
# 필요 시(키 없이 health만 띄우고 싶을 때) 환경변수 ALLOW_NO_KEY=1 로 우회 가능
if not API_KEY and os.getenv("ALLOW_NO_KEY") != "1":
    raise RuntimeError(
        "OPENAI_API_KEY 환경변수가 설정되지 않았습니다.\n"
        "PowerShell 예: $env:OPENAI_API_KEY=\"sk-...\"\n"
        "또는 (임시 우회) ALLOW_NO_KEY=1"
    )


app = FastAPI(title="Quiz Local AI Server", version="1.0")

# CORS: GitHub Pages(서비스)에서만 호출하도록 제한 + 로컬 개발 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://allenkim.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Render 기본 헬스체크(/) 대응 + 간단한 동작 확인용."""
    return {"ok": True, "service": "civil-law-quiz-ai"}


class ChatIn(BaseModel):
    message: str
    context: str
    previous_response_id: Optional[str] = None


class ChatOut(BaseModel):
    reply: str
    previous_response_id: Optional[str] = None


@app.get("/health")
def health():
    return {"ok": True, "openai_key_loaded": bool(API_KEY)}


@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai 패키지를 불러오지 못했습니다. (pip install openai)")

    client = OpenAI(api_key=API_KEY)

    # 튜터 스타일: 해설을 그대로 두고, 이해를 돕는 추가 설명만
    instructions = (
        "너는 공인중개사 민법 시험 대비 튜터다. "
        "사용자가 첨부한 '문제/보기/정답/해설(원문)'을 기반으로, "
        "해설을 그대로 반복하기보다는 '왜 그런지'를 쉽게 풀어서 설명한다. "
        "필요하면 예시를 1개만 들고, 마지막에 한 줄 요약을 붙인다."
    )

    user_input = (
        payload.context.strip()
        + "\n\n[사용자 질문]\n"
        + payload.message.strip()
    )

    try:
        # Responses API 사용 (멀티턴은 previous_response_id로 이어붙일 수 있음)
        resp = client.responses.create(
            model=DEFAULT_MODEL,
            instructions=instructions,
            input=user_input,
            previous_response_id=payload.previous_response_id,
            store=True,
        )
        return ChatOut(
            reply=getattr(resp, "output_text", "") or "",
            previous_response_id=getattr(resp, "id", None),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat_stream")
def chat_stream(payload: ChatIn):
    """SSE 스트리밍 응답.
    프론트에서 /chat_stream 으로 POST하면,
    - status: 진행 상태
    - delta: 토큰 스트리밍
    - done: 완료
    이벤트를 순차적으로 반환합니다.
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai 패키지를 불러오지 못했습니다. (pip install openai)")

    client = OpenAI(api_key=API_KEY)

    # 튜터 스타일: 해설을 그대로 두고, 이해를 돕는 추가 설명만
    instructions = (
        "너는 공인중개사 민법 시험 대비 튜터다. "
        "사용자가 첨부한 '문제/보기/정답/해설(원문)'을 기반으로, "
        "해설을 그대로 반복하기보다는 '왜 그런지'를 쉽게 풀어서 설명한다. "
        "필요하면 예시를 1개만 들고, 마지막에 한 줄 요약을 붙인다."
    )

    user_input = (
        payload.context.strip()
        + "\n\n[사용자 질문]\n"
        + payload.message.strip()
    )

    def event_gen():
        # UX용 진행 로그 (모델의 내부 추론을 그대로 노출하지 않음)
        yield _sse({"type": "status", "text": "질문을 해석하는 중…"})
        time.sleep(0.15)
        yield _sse({"type": "status", "text": "관련 근거를 정리하는 중…"})
        time.sleep(0.15)
        yield _sse({"type": "status", "text": "답변을 작성하는 중…"})
        time.sleep(0.05)

        try:
            stream = client.responses.create(
                model=DEFAULT_MODEL,
                instructions=instructions,
                input=user_input,
                previous_response_id=payload.previous_response_id,
                stream=True,
                store=True,
            )

            for event in stream:
                et = getattr(event, "type", None)

                # 토큰 델타(타이핑 효과)
                if et in ("response.output_text.delta", "output_text.delta"):
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        yield _sse({"type": "delta", "text": delta})

                # 응답 완료
                elif et in (
                    "response.completed",
                    "response.done",
                    "response.output_text.done",
                ):
                    break

            yield _sse({"type": "done"})

        except Exception as e:
            yield _sse({"type": "error", "text": str(e)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ai_server_2:app", host=APP_HOST, port=APP_PORT, reload=(os.getenv("UVICORN_RELOAD") == "1"))
