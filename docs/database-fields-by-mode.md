# Database Fields by Mode

## Collections Used Across All Modes

### `user_event_tracking` (per-user state)

| Field | Purpose |
|---|---|
| `phone` | Normalized phone number (query key) |
| `user_id` | UUID matching document ID |
| `events` | Array of `{event_id, timestamp}` — events the user has joined |
| `current_event_id` | Active event |
| `awaiting_event_id` | Flag: waiting for user to input an event ID |
| `awaiting_event_change_confirmation` | Flag: waiting for confirmation to switch events |
| `last_inactivity_prompt` | Timestamp of last inactivity nudge |
| `awaiting_extra_questions` | Flag: in the extra questions (demographics) flow |
| `current_extra_question_index` | Progress through extra questions |
| `invalid_attempts` | Count of invalid event selection attempts |

### `elicitation_bot_events/{event_id}` (event config, read by all modes)

| Field | Purpose |
|---|---|
| `mode` | "survey" / "followup" / "listener" |
| `event_name`, `event_location`, `event_date`, `event_background` | Event metadata |
| `languages` | Supported languages |
| `welcome_message`, `initial_message`, `completion_message` | Scripted messages |
| `extra_questions` | Demographic questions shown to all users before main flow |
| `interaction_limit` | Max interactions before cutoff |

---

## Survey Mode

**Unique event config fields:**

| Field | Purpose |
|---|---|
| `questions` | Array of `{id, text, asked_count}` — the survey questions to rotate through |

**Participant doc fields** (`participants/{uuid}`):

| Field | Purpose |
|---|---|
| `questions_asked` | Map of `{question_id: bool}` — which questions have been answered |
| `responses` | Map of `{question_id: response}` — stores the actual answers |
| `last_question_id` | Currently active question in the flow |
| `survey_complete` | Boolean — marks survey as finished |
| `interactions` | Full conversation history `{message, response, ts}` |
| `[extra_question_key]` | Values for demographic answers (e.g., `name`, `age`) |

---

## Followup Mode

**Unique event config fields:**

| Field | Purpose |
|---|---|
| `bot_topic`, `main_question`, `bot_aim` | Core LLM instructions |
| `bot_principles`, `bot_personality`, `bot_additional_prompts` | Shapes bot behavior |
| `follow_up_questions` | `{enabled, questions}` — dynamic follow-up prompts |
| `language_guidance` | Instructions for how bot handles language switching |
| `default_model` | Which LLM model to use |
| `second_round_claims_source` | `{enabled, collection, document}` — points to a claims bank |
| `second_round_prompts` | `{system_prompt, user_prompt}` for 2nd round |

**Participant doc fields** (`participants/{uuid}`):

| Field | Purpose |
|---|---|
| `interactions` | `{message, response, model, fallback, ts}` — conversation history + LLM metadata |
| `summary` | Bot-generated summary of user's perspective (2nd round) |
| `agreeable_claims` / `opposing_claims` | Claims selected for the user to react to (2nd round) |
| `claim_selection_reason` | Why those claims were selected |
| `second_round_interactions` | Separate interaction log for 2nd round |
| `second_round_intro_done` | Flag: 2nd round intro already shown |

---

## Listener Mode

Shares nearly all fields with Followup mode, but without the structured bot personality fields (`bot_topic`, `bot_aim`, `bot_principles`, etc.). It has a more passive posture — the bot listens rather than steering conversation.

**Event config fields used:**
- Same base fields as all modes
- `language_guidance`, `default_model`
- Full second round fields (`second_round_claims_source`, `second_round_prompts`)

**Participant doc fields:** Identical structure to Followup mode (including second round fields).

---

## Key Differences

| | Survey | Followup | Listener |
|---|---|---|---|
| Question tracking | `questions_asked`, `responses`, `last_question_id` | None | None |
| Completion trigger | All questions answered | User says "finish" | User says "finish" |
| LLM model field | Not used | `default_model` | `default_model` |
| Bot personality config | None | Full (`bot_aim`, `bot_principles`, etc.) | Minimal |
| Second round support | No | Yes | Yes |
| `interactions` shape | `{message, response, ts}` | `{message, response, model, fallback, ts}` | Same as followup |
