"""Chat agent: LLM tool loop. ALL tool calls go through the gateway router (control plane),
under the authenticated user's identity and role."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..models.tables import User
from ..auth.rbac import current_user
from ..routing import router as R
from ..config import ANTHROPIC_API_KEY, CHAT_MODEL

api = APIRouter(prefix="/api")

class ChatIn(BaseModel):
    messages: list[dict]   # [{"role":"user","content":"..."}]

@api.post("/chat")
async def chat(b: ChatIn, u: User = Depends(current_user)):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]} for t in R.tools_for(u)]
    msgs, trace = list(b.messages), []
    system = f"You are the Urumi assistant for {u.name or u.email}. Use tools when needed. Today is {__import__('datetime').date.today().isoformat()}."
    async with httpx.AsyncClient(timeout=60) as c:
        for _ in range(6):
            r = await c.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                json={"model": CHAT_MODEL, "max_tokens": 1024, "system": system, "tools": tools, "messages": msgs})
            if r.status_code != 200: raise HTTPException(502, f"LLM error: {r.text[:200]}")
            data = r.json(); msgs.append({"role": "assistant", "content": data["content"]})
            uses = [x for x in data["content"] if x["type"] == "tool_use"]
            if not uses:
                return {"reply": "".join(x.get("text", "") for x in data["content"] if x["type"] == "text"), "tool_trace": trace}
            results = []
            for tu in uses:
                res = await R.execute(u, tu["name"], tu["input"], "chat")
                trace.append({"tool": tu["name"], "input": tu["input"], "isError": res["isError"]})
                text = "\n".join(x.get("text", "") for x in res["content"] if x.get("type") == "text")
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": text or "(no output)", "is_error": res["isError"]})
            msgs.append({"role": "user", "content": results})
    return {"reply": "Stopped after tool-loop limit.", "tool_trace": trace}
