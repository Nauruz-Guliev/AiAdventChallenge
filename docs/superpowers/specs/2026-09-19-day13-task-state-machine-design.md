# Day 13 — Task State Machine: Design Spec

Date: 2026-09-19
Status: approved

## Goal

Formalize the task lifecycle of the assistant as a finite state machine (FSM):
stage (planning → execution → validation → done), current step, expected action.
The user can pause the task on any stage and resume it without the agent
re-explaining what was already said.

## Scope

- New project `day13/` scaffolded from `day12/` (profiles and memory stay inside
  the agent as baseline mechanics; the star of day 13 is the FSM).
- One active task at a time. `done` + next user message starts a new task cycle.
- Deterministic FSM: the backend owns all transitions; the LLM only supplies
  content (plan steps, step answers, validation report).

## Architecture

- `backend/app/domain/task_state.py` — pure domain FSM, no HTTP/LLM imports:
  - `Stage` enum: `PLANNING`, `EXECUTION`, `VALIDATION`, `DONE`.
  - `TaskState`: `stage`, `step` (0-based index of current step), `total_steps`,
    `steps` (list of labels), `expected_action`, `paused`.
  - Transition table: forward-only
    `PLANNING → EXECUTION → VALIDATION → DONE`; pause is an orthogonal flag
    valid on any non-DONE stage (pause on DONE and resume while not paused are
    no-ops). Invalid transitions raise `InvalidTransitionError`.
  - Methods: `start_planning()`, `accept_plan(steps)`, `advance_step()`,
    `enter_validation()`, `finish()` (also clears the pause flag), `pause()`,
    `resume()`.
- `backend/app/infrastructure/json_task_repository.py` — persists `TaskState`
  (+ task description) to `backend/data/task_state.json` using the existing
  `json_store.py` pattern. Survives backend restart and page reload.
- `backend/app/application/task_engine.py` — orchestrates chat turns:
  1. If paused → short-circuit: return fixed pause notice, no LLM call.
  2. If no active task or `DONE` → start `PLANNING`.
  3. Build the system prompt with current stage, step, task description,
     and (on resume) "continue from step X, do not repeat the plan or earlier
     explanations".
  4. Call the LLM gateway (existing port), parse the reply per stage:
     - PLANNING: expect a fenced JSON array of step labels. Parsed → `accept_plan`,
       stage becomes EXECUTION, step 0, expected action "агент выполняет шаг 1".
       Parse failure → one automatic retry with a format hint; still bad →
       stay in PLANNING with the raw reply shown.
     - EXECUTION: the reply is exactly one step. After it, step +1;
       after the last step → VALIDATION.
     - VALIDATION: one reply = validation report → DONE.
  5. Persist after every transition.
- API (extend `presentation/routes.py`):
  - `GET /api/task/state` → `TaskState` + stage labels.
  - `POST /api/task/pause`, `POST /api/task/resume`.
  - `POST /api/chat` consults the engine (paused / FSM advance) on top of the
    existing profile/memory injection.

## Frontend

- New `components/TaskStatePanel.jsx` above the chat, in the day-12 style
  (no gradients, one mint accent, `--surface-2` fields):
  - Stepper of 4 stages (планирование → выполнение → проверка → готово);
    active stage highlighted, completed ones ticked.
  - Line "Шаг X/N — <step label>".
  - Line "Ожидается: <expected_action>".
  - Button «Пауза»; when paused: badge «НА ПАУЗЕ» and «Продолжить».
- `api.js`: `getTaskState`, `pauseTask`, `resumeTask`.
- The panel renders after the first task is created; state refreshes after each
  chat reply and on resume/pause.

## Error handling

- Bad plan JSON: one automatic retry with a stricter instruction; if it still
  fails, remain in PLANNING (state never silently corrupts).
- LLM gateway failure: state does not advance; error surfaces in the chat as in
  day 12.
- Pause blocks only agent work; user messages are still accepted and answered
  with the fixed notice.

## Testing

- Unit (pure FSM): transition legality (no skipping, no going backwards),
  step advancement, plan acceptance, pause/resume preserving stage and step,
  done → new task resets state, invalid transitions raise.
- Repository: save/load roundtrip, missing-file → fresh state.
- API + engine with a fake LLM gateway: new task → planning; valid plan →
  execution; step-by-step advancement; validation → done; paused chat returns
  notice without calling the gateway; resume continues at the same step.
- Frontend: `npm run build`.

## Live check (for the video)

1. Send a task → state: планирование, "ожидается: агент составляет план".
2. Agent returns plan (3 steps) → состояние: выполнение, шаг 1/3.
3. Pause during step 2 → agent refuses to work («задача на паузе»).
4. Resume → "продолжай" → agent continues at step 2/3 without re-explaining
   the plan.
5. After step 3 → проверка → done.
