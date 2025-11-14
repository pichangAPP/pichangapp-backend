## 📂 `docs/` – The Agent's Knowledge Base (optional)

If your agent answers knowledge-based questions (FAQs, policies, etc.), you can put markdown, PDFs, or text files in this folder. Rasa can use this content for retrieval-augmented responses if set up with a vector store [2](https://rasa.com/docs/pro/build/retrieval-actions).

**Edit here** to update what your agent can retrieve and summarize for users.

## 🧠 Context for the Pichanga assistant

This folder also doubles as a lightweight briefing for the action server and conversational designers. The current assistant needs to juggle two personas:

- **Players:** friendly tone, eager to help with field recommendations, reservations, or FAQs. They should always hear player-specified greetings and prompts (`utter_hello`, `utter_what_can_you_do`, etc.), and the conversation follows the `request_field_recommendation` flow.
- **Administrators:** respectful, formal tone. Admins get the admin-specific clauses in the same `utter_*` responses when `user_role=admin`. The `request_admin_recommendation` intent now covers strategies such as dynamic pricing adjustments and schedule changes, and `action_provide_admin_management_tips` adds detailed tips for occupancy/demand.

### Key behavioral points

1. **Role detection is enforced early** via `action_ensure_user_role` so every rule reads a slot that matches their JWT before the greeting/help action runs.
2. **NLU coverage**: `nlu.yml` includes player-friendly synonyms (“habla”, “Dime”, “necesito un favor”, etc.) plus admin-specific phrases about prices, demand, and schedule.
3. **Analytics integration**: the admin action fetches campus top clients using the analytics service, passing the bearer token stored in metadata for access control. Make sure telemetry keeps the `managed_campus_*` slots updated on session start.
4. **Admin tip stories:** Two new boosted tips cover the user stories “precios dinámicos según demanda/hora” and “ajustes de horario para mejorar ocupación”. They are triggered whenever the admin intent runs and mention `target_time` or general blocks.

### How to add more context

- Update the examples in `nlu.yml` whenever you introduce a new phrasing so the role detection stays sharp.
- Keep responses `utter_*` localized in `domain.yml`, using slot conditions to swap between admin and player tone.
- When you add new actions, document them here, describe which intents trigger them, and note any metadata they require (e.g., bearer tokens, campus IDs).

Use this doc as the single source of truth for how the assistant must behave across roles, analytics, and pricing stories.
