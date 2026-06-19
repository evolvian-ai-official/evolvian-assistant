import json
from fastapi import APIRouter, HTTPException

from api.config.config import supabase
from api.evoin.claude_client import get_claude, EVOIN_MODEL, SYSTEM_ANALYZER

router = APIRouter(prefix="/api/evoin", tags=["EvoIn Analysis"])


@router.post("/interviews/{interview_id}/analyze")
def run_aggregate_analysis(interview_id: str, founder_token: str):
    iv = (
        supabase.table("evoin_interviews")
        .select("*")
        .eq("id", interview_id)
        .eq("founder_token", founder_token)
        .single()
        .execute()
    )
    if not iv.data:
        raise HTTPException(404, "Interview not found")

    sessions = (
        supabase.table("evoin_sessions")
        .select("*")
        .eq("interview_id", interview_id)
        .not_.is_("completed_at", "null")
        .execute()
    )
    completed = sessions.data or []

    if len(completed) < 2:
        raise HTTPException(400, "Need at least 2 completed interviews to run aggregate analysis")

    # Build transcripts block
    transcripts_text = ""
    for i, s in enumerate(completed, 1):
        lines = "\n".join(
            f"  P: {r['question_text']}\n  R: {r['answer']}"
            for r in (s.get("responses") or [])
        )
        transcripts_text += f"\n--- Entrevista {i} ---\n{lines}\n"

    prompt = f"""Analiza estas {len(completed)} transcripciones de entrevistas Mom Test de forma agregada.

Hipótesis del founder: "{iv.data['hypothesis']}"
Segmento: {iv.data['segment']}

Transcripciones:
{transcripts_text}

Responde con este JSON exacto:
{{
  "total_sessions": {len(completed)},
  "patterns": [
    {{"signal_type": "pain"|"job"|"buy"|"quote"|"warn", "text": "descripción", "count": N, "total": {len(completed)}}}
  ],
  "hypothesis_status": "validated"|"invalidated"|"pivot_needed",
  "hypothesis_evidence": "evidencia directa citando respuestas reales",
  "pivot_suggestion": "si pivot_needed, qué debería refinar el founder (o null)",
  "wtp_estimate": "estimación basada en gasto actual mencionado",
  "pain_confirmed_count": N,
  "already_paying_count": N,
  "avg_spend": "gasto promedio mencionado o null",
  "next_actions": [
    "acción concreta 1",
    "acción concreta 2",
    "acción concreta 3"
  ]
}}"""

    claude = get_claude()
    resp = claude.messages.create(
        model=EVOIN_MODEL,
        max_tokens=2500,
        system=SYSTEM_ANALYZER,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw)

    saved = supabase.table("evoin_analysis").insert({
        "interview_id": interview_id,
        "session_id": None,
        "type": "aggregate",
        "result": result,
    }).execute()

    return {"analysis": saved.data[0]}
