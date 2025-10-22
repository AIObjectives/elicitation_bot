import openai
from typing import List
from config.config import db, logger, client

openai.api_key = "sk-YOUR-KEY-HERE"  # Replace with your key

def _summarize_user_messages(messages: List[str]) -> str:
    if not messages:
        return "No messages to summarize."

    system_message = (
        "You are a neutral assistant tasked with summarizing a user's perspective. "
        "Write a clear and concise summary in 1–2 sentences, preserving tone and core themes."
    )

    user_input = "Here are the user's messages:\n\n" + "\n".join(f"- {m}" for m in messages if m)

    try:
        
        resp = client.chat.completions.create(
            model="gpt-4o",  # You can use gpt-4o-mini if needed
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        return (resp.choices[0].message["content"] or "").strip() or "Summary unavailable."
    except Exception as e:
        print(f"[ERROR] OpenAI: {e}")
        return "⚠️ Error generating summary."


# --- Scenario A: Neutral positive feedback ---
scenario_a = [
    "I loved the event. Everything felt smooth.",
    "I learned a lot from the speakers.",
    "The flow of the session was perfect."
]

# --- Scenario B: Mixed feedback with concern ---
scenario_b = [
    "The event was okay, but it started late.",
    "Some parts were confusing, but overall it was fine.",
    "I'm not sure everyone had the chance to participate."
]

# --- Scenario C: Highly negative or critical ---
scenario_c = [
    "The session was very disorganized.",
    "I didn’t find the content useful.",
    "The facilitator didn’t engage with us properly."
]

print("--- Scenario A Summary ---")
print(_summarize_user_messages(scenario_a))

print("\n--- Scenario B Summary ---")
print(_summarize_user_messages(scenario_b))

print("\n--- Scenario C Summary ---")
print(_summarize_user_messages(scenario_c))