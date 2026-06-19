import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.config.config import supabase
from api.evoin.claude_client import get_claude, EVOIN_MODEL, SYSTEM_DEEPENING

router = APIRouter(prefix="/api/evoin", tags=["EvoIn Sessions"])


class StartSessionPayload(BaseModel):
    interview_id: str


class RespondPayload(BaseModel):
    question_id: int
    question_text: str
    answer: str
    is_followup: bool = False


@router.post("/sessions")
def start_session(payload: StartSessionPayload):
    # Verify interview exists and is active
    iv = (
        supabase.table("evoin_interviews")
        .select("id, status")
        .eq("id", payload.interview_id)
        .single()
        .execute()
    )
    if not iv.data:
        raise HTTPException(404, "Interview not found")
    if iv.data["status"] != "active":
        raise HTTPException(410, "Interview is no longer active")

    result = (
        supabase.table("evoin_sessions")
        .insert({"interview_id": payload.interview_id, "responses": []})
        .execute()
    )
    return {"session": result.data[0]}


@router.post("/sessions/{session_id}/respond")
def submit_response(session_id: str, payload: RespondPayload):
    # Load session
    sess = (
        supabase.table("evoin_sessions")
        .select("*")
        .eq("id", session_id)
        .single()
        .execute()
    )
    if not sess.data:
        raise HTTPException(404, "Session not found")
    if sess.data.get("completed_at"):
        raise HTTPException(409, "Session already completed")

    # Decide: deepen or continue
    claude = get_claude()
    deepen_prompt = f"""Pregunta: {payload.question_text}
Respuesta del entrevistado: {payload.answer}
¿Es suficientemente detallada o necesita profundización?"""

    deepen_resp = claude.messages.create(
        model=EVOIN_MODEL,
        max_tokens=300,
        system=SYSTEM_DEEPENING,
        messages=[{"role": "user", "content": deepen_prompt}],
    )
    raw = deepen_resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    decision = json.loads(raw)

    # Append response to session
    responses = sess.data.get("responses") or []
    responses.append({
        "question_id": payload.question_id,
        "question_text": payload.question_text,
        "answer": payload.answer,
        "is_followup": payload.is_followup,
        "deepening_action": decision["action"],
    })

    supabase.table("evoin_sessions").update({"responses": responses}).eq("id", session_id).execute()

    return {
        "action": decision["action"],
        "message": decision["message"],
    }


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str):
    sess = (
        supabase.table("evoin_sessions")
        .select("id, interview_id, responses")
        .eq("id", session_id)
        .single()
        .execute()
    )
    if not sess.data:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("evoin_sessions").update({"completed_at": now}).eq("id", session_id).execute()

    # Trigger individual analysis async-ish (inline for MVP)
    _run_individual_analysis(sess.data)

    return {"status": "completed"}


def _run_individual_analysis(session: dict):
    """Runs individual analysis for a single session and stores the result."""
    iv = (
        supabase.table("evoin_interviews")
        .select("hypothesis, segment")
        .eq("id", session["interview_id"])
        .single()
        .execute()
    )
    if not iv.data:
        return

    transcript = "\n".join(
        f"Pregunta: {r['question_text']}\nRespuesta: {r['answer']}"
        for r in session["responses"]
    )

    prompt = f"""Analiza esta transcripción de entrevista Mom Test.

Hipótesis del founder: "{iv.data['hypothesis']}"
Segmento: {iv.data['segment']}

Transcripción:
{transcript}

Responde con este JSON:
{{
  "summary": "resumen ejecutivo en 3-4 oraciones",
  "signals": [
    {{"type": "pain"|"job"|"buy"|"quote"|"warn", "text": "descripción de la señal"}}
  ],
  "wtp_estimate": "estimación de willingness to pay o null si no hay datos",
  "hypothesis_status": "validates"|"invalidates"|"pivot_needed",
  "hypothesis_evidence": "cita o evidencia directa de la transcripción"
}}"""

    claude = get_claude()
    resp = claude.messages.create(
        model=EVOIN_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw)

    supabase.table("evoin_analysis").insert({
        "interview_id": session["interview_id"],
        "session_id": session["id"],
        "type": "individual",
        "result": result,
    }).execute()
