import os
import textwrap
from typing import List, Dict, Any, Optional
from openai import OpenAI

# =========================
# CONFIG (edit these)
# =========================
OPENAI_API_KEY = "xxx"  # <-- hard-code for fast local testing only
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.35
MAX_TOKENS = 220

# Optional: small metadata blob that would normally come from your report doc
DEFAULT_METADATA = {
    "title": "AI & Work Futures",
    "date": "2025-08-01",
    "source_count": 17,
}

# =========================
# LLM CLIENT
# =========================
def get_client() -> OpenAI:
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-REPLACE"):
        raise RuntimeError("Please set OPENAI_API_KEY at the top of the file.")
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    return OpenAI(api_key=OPENAI_API_KEY)

# =========================
# PROMPT COMPOSER (same logic as prod, minus Firestore)
# =========================
def build_second_round_message(
    user_msg: str,
    summary: str,
    agreeable: List[str],
    opposing: List[str],
    metadata: Dict[str, Any],
    claim_selection_reason: Optional[str] = None,
    recent_turns: Optional[List[Dict[str, str]]] = None,
    intro_done: bool = False,
) -> str:

    # History block
    history_block = ""
    if recent_turns:
        parts = []
        for t in recent_turns[-6:]:
            role = "User" if t.get("role") == "user" else "Assistant"
            text = " ".join(str(t.get("text", "")).split())
            if len(text) > 220:
                text = text[:220] + "…"
            parts.append(f"{role}: {text}")
        history_block = "Recent Dialogue (latest last):\n" + "\n".join(parts) + "\n\n"

    # Claims visibility
    if intro_done:
        agree_block  = "(hidden—show only if user asks)"
        oppose_block = "(hidden—show only if user asks)"
    else:
        agree_block  = "\n".join(agreeable[:2]) if agreeable else "(none)"
        oppose_block = "\n".join(opposing[:2])  if opposing  else "(none)"

    reason_line = f"\nClaim selection note: {claim_selection_reason}" if (claim_selection_reason and not intro_done) else ""

    system_prompt = (
        "You are a concise, context-aware *second-round deliberation* assistant.\n"
        "Goals: keep flow natural, avoid repetition, and deepen the user's thinking with concrete contrasts.\n"
        "Hard rules:\n"
        "- NEVER re-introduce the whole setup after the intro.\n"
        "- Keep replies short: 1–4 crisp sentences, <= ~400 characters total.\n"
        "- Answer the user's exact question first; then, if helpful, add ONE brief nudge.\n"
        "- Do not ask generic questions like 'What aspect...?'—be specific and grounded.\n"
        "- Only restate claims if the user asks for them.\n"
    )

    user_prompt = (
        f"{history_block}"
        f"User Summary: {summary}\n"
        f"Report Metadata (context only): {metadata}\n"
        f"Agreeable (grounding): {agree_block}\n"
        f"Opposing (grounding): {oppose_block}"
        f"{reason_line}\n\n"
        f"Current user message: {user_msg}\n\n"
        "Respond now following the rules above. If the user asks 'what are we doing', reply with ONE sentence and pivot to a pointed follow-up.\n"
        "If the user asks whether you can access others' reports, answer briefly: you have curated claims (not direct personal data), then offer a one-line, targeted next step.\n"
        "When relevant, introduce another participant’s claim naturally, e.g., 'Here’s something that aligns with your view—do you agree?' or 'Here’s an opposing view—how would you respond?'\n"
    )

    return system_prompt, user_prompt

def call_llm(client: OpenAI, system_prompt: str, user_prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return (resp.choices[0].message.content or "").strip()

# =========================
# SCENARIOS (edit/add freely)
# =========================
SCENARIOS = [
    {
        "name": "Scenario 1 — Remote work optimism",
        "summary": "User believes remote work boosts productivity and inclusion when teams have clear norms.",
        "agreeable_claims": [
            "- [12] Remote-first teams report higher focus due to fewer interruptions.",
            "- [44] Parents and caregivers report improved participation with async work."
        ],
        "opposing_claims": [
            "- [7] Innovation cadence dips when spontaneous in-person exchanges vanish.",
            "- [29] New hires ramp slower without co-located mentorship."
        ],
        "reason": "Gives a clean pro/contra contrast on productivity vs. collaboration costs.",
        "recent_turns": [
            {"role": "user", "text": "I get way more done at home than in an open office."},
            {"role": "assistant", "text": "What tradeoffs do you notice on collaboration?"}
        ],
        "user_msg": "Yeah, collaboration is tricky, but it's solvable with the right rituals. what do others say exactly and i love nutella"
    },
    {
        "name": "Scenario 2 — AI hiring concerns",
        "summary": "User is worried AI screening tools encode bias and reduce candidate diversity.",
        "agreeable_claims": [
            "- [3] Legacy datasets mirror historic bias and skew rankings.",
            "- [18] Opaque models hinder appeals for rejected candidates."
        ],
        "opposing_claims": [
            "- [21] Consistent automated rubrics reduce ad-hoc interviewer bias.",
            "- [36] Post-hoc audits can flag disparate impact earlier than humans."
        ],
        "reason": "Balance fairness risks with potential for consistency and auditing.",
        "recent_turns": [],
        "user_msg": "How can we keep the speed benefits without unfairness?"
    },
    # {
    #     "name": "Scenario 3 — Open-source vs. proprietary",
    #     "summary": "User favors open-source models for transparency and safety research.",
    #     "agreeable_claims": [
    #         "- [5] Community scrutiny catches failure modes faster.",
    #         "- [16] Reproducibility enables independent safety evaluation."
    #     ],
    #     "opposing_claims": [
    #         "- [22] Open weights may ease misuse for capable attackers.",
    #         "- [41] Fragmentation slows standardization and governance."
    #     ],
    #     "reason": "Highlights the transparency vs. misuse tension.",
    #     "recent_turns": [{"role": "user", "text": "Closed labs aren’t accountable enough."}],
    #     "user_msg": "Isn’t openness the safer long-term bet?"
    # },
    # {
    #     "name": "Scenario 4 — Data privacy tradeoffs",
    #     "summary": "User wants strict data minimization; skeptical of 'consent' banners.",
    #     "agreeable_claims": [
    #         "- [9] Minimization reduces breach blast radius and liability.",
    #         "- [27] People rarely read consent dialogs; defaults do the real work."
    #     ],
    #     "opposing_claims": [
    #         "- [14] Rich telemetry can prevent fraud and abuse at scale.",
    #         "- [33] Personalization raises engagement for underserved users."
    #     ],
    #     "reason": "Contrast safety vs. utility with real operational pressures.",
    #     "recent_turns": [],
    #     "user_msg": "What safeguards would make richer telemetry acceptable?"
    # },
    # {
    #     "name": "Scenario 5 — AI in classrooms",
    #     "summary": "User supports AI tutors for scaffolding but fears shortcutting learning.",
    #     "agreeable_claims": [
    #         "- [6] Step-by-step hints improve outcomes for struggle points.",
    #         "- [30] 24/7 availability expands support beyond teacher hours."
    #     ],
    #     "opposing_claims": [
    #         "- [19] Over-reliance reduces retrieval practice and mastery.",
    #         "- [25] Tutoring quality varies; hallucinations can mislead."
    #     ],
    #     "reason": "Juxtaposes access benefits with deep-learning risks.",
    #     "recent_turns": [
    #         {"role": "assistant", "text": "Which subjects benefit most for your students?"}
    #     ],
    #     "user_msg": "Math and writing—kids get stuck differently in each."
    # },
    # {
    #     "name": "Scenario 6 — Regulate frontier models",
    #     "summary": "User wants licensing for frontier AI; believes voluntary codes are weak.",
    #     "agreeable_claims": [
    #         "- [8] Safety evaluations lack teeth without enforcement.",
    #         "- [31] Shared incident reporting improves ecosystem learning."
    #     ],
    #     "opposing_claims": [
    #         "- [13] Heavy licenses can entrench incumbents and slow entrants.",
    #         "- [24] Global compliance mismatch invites regulatory arbitrage."
    #     ],
    #     "reason": "Show enforcement vs. innovation/competition tension.",
    #     "recent_turns": [],
    #     "user_msg": "What would a narrow, workable license look like?"
    # },
]

# =========================
# MAIN
# =========================
def run():
    client = get_client()

    print("\n=== Second-Round LLM Smoke Test ===\n")
    for i, sc in enumerate(SCENARIOS, start=1):
        system_prompt, user_prompt = build_second_round_message(
            user_msg=sc["user_msg"],
            summary=sc["summary"],
            agreeable=sc["agreeable_claims"],
            opposing=sc["opposing_claims"],
            metadata=DEFAULT_METADATA,
            claim_selection_reason=sc.get("reason"),
            recent_turns=sc.get("recent_turns"),
            intro_done=False,  # first turn style
        )

        print(f"--- {i}. {sc['name']} ---")
        # For transparency, you can print a small view of the prompt (optional)
        # print(textwrap.indent(user_prompt[:600] + ('…' if len(user_prompt)>600 else ''), prefix='> '))
        try:
            out = call_llm(client, system_prompt, user_prompt)
            print(textwrap.fill(out, width=100))
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
        print()

    print("=== Done ===")

if __name__ == "__main__":
    run()
