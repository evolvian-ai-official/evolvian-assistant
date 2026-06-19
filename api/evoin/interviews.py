import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.config.config import supabase
from api.evoin.claude_client import get_claude, EVOIN_MODEL, SYSTEM_QUESTION_GENERATOR

router = APIRouter(prefix="/api/evoin", tags=["EvoIn"])

DEPTH_MAP = {6: "Exploratoria (~10 min)", 10: "Estándar (~20 min)", 15: "Profunda (~30 min)"}


class CreateInterviewPayload(BaseModel):
    hypothesis: str
    segment: str
    depth: int = 10
    founder_token: str | None = None


@router.post("/interviews")
def create_interview(payload: CreateInterviewPayload):
    if payload.depth not in DEPTH_MAP:
        raise HTTPException(400, "depth must be 6, 10, or 15")

    founder_token = payload.founder_token or str(uuid.uuid4())

    prompt = f"""Genera exactamente {payload.depth} preguntas de entrevista Mom Test para este segmento e hipótesis.

Hipótesis del founder (SOLO para contexto — NUNCA la menciones en las preguntas):
"{payload.hypothesis}"

Segmento a entrevistar: {payload.segment}

Responde con este JSON exacto:
{{
  "questions": [
    {{"id": 1, "text": "pregunta aquí"}},
    ...
  ],
  "welcome_message": "Un fundador quiere entender tu día a día como {payload.segment}. Son {payload.depth} preguntas, sin respuestas correctas."
}}"""

    claude = get_claude()
    response = claude.messages.create(
        model=EVOIN_MODEL,
        max_tokens=2000,
        system=SYSTEM_QUESTION_GENERATOR,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code blocks if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    generated = json.loads(raw)

    result = (
        supabase.table("evoin_interviews")
        .insert({
            "founder_token": founder_token,
            "hypothesis": payload.hypothesis,
            "segment": payload.segment,
            "depth": payload.depth,
            "questions": generated["questions"],
            "status": "active",
        })
        .execute()
    )

    interview = result.data[0]
    return {
        "interview": interview,
        "welcome_message": generated["welcome_message"],
        "founder_token": founder_token,
        "share_link_path": f"/i/{interview['id']}",
    }


@router.get("/interviews")
def list_interviews(founder_token: str):
    if not founder_token:
        raise HTTPException(400, "founder_token required")

    rows = (
        supabase.table("evoin_interviews")
        .select("*, evoin_sessions(id, completed_at, started_at)")
        .eq("founder_token", founder_token)
        .order("created_at", desc=True)
        .execute()
    )
    return {"interviews": rows.data}


@router.get("/interviews/{interview_id}")
def get_interview(interview_id: str, founder_token: str):
    row = (
        supabase.table("evoin_interviews")
        .select("*")
        .eq("id", interview_id)
        .eq("founder_token", founder_token)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Interview not found")

    sessions = (
        supabase.table("evoin_sessions")
        .select("*")
        .eq("interview_id", interview_id)
        .execute()
    )

    analyses = (
        supabase.table("evoin_analysis")
        .select("*")
        .eq("interview_id", interview_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "interview": row.data,
        "sessions": sessions.data,
        "analyses": analyses.data,
    }


# Public endpoint — no founder_token needed (participant reads the interview)
@router.get("/public/interviews/{interview_id}")
def get_public_interview(interview_id: str):
    row = (
        supabase.table("evoin_interviews")
        .select("id, segment, depth, questions, status")
        .eq("id", interview_id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Interview not found")
    if row.data["status"] != "active":
        raise HTTPException(410, "This interview is no longer active")
    return row.data
