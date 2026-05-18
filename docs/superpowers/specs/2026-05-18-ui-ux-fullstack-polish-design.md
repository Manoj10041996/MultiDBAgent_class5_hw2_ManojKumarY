# UI/UX Full-Stack Polish Design (Balanced)

Date: 2026-05-18
Scope: UI/UX upgrade + frontend architecture cleanup + backend/test stability checks (no new guardrails)

## 1. Objectives

1. Make the chat UI more interactive, user-friendly, and visually attractive.
2. Refactor frontend structure for maintainability without changing API behavior.
3. Keep backend/API stable and ensure frontend/backend/tests remain healthy.

## 2. Constraints and Alignment

1. Keep API contract from SPEC.md unchanged:
   - `POST /chat`
   - Response fields: `answer`, `tool_calls`, `warnings`, `elapsed_ms`
2. Preserve single-turn behavior and tool-trace transparency.
3. No new guardrail feature work in this pass.
4. Align architecture with current module boundaries:
   - Backend API split (`backend/api/*`) and thin `backend/main.py` entrypoint.
5. Changes must remain compatible with HLD and LLD intent, with docs updated where needed.

## 3. Proposed Architecture Changes

### 3.1 Frontend Component Decomposition

Refactor current `frontend/src/App.tsx` into focused modules:

1. `AppShell`
- Global page frame, header, and responsive layout regions.

2. `ChatPage`
- Orchestrates chat flow and composes message list + composer + suggestion chips.

3. `useChatSession` hook
- Owns chat state: `messages`, `input`, `isLoading`, `error`.
- Exposes actions: `submitQuestion`, `retryLast`, `setInput`, `clearChat`.

4. `MessageList`
- Renders conversation rows, loading row, warning row, error row.

5. `Composer`
- Textarea behavior (auto-grow, key handling, disabled states, send button states).

6. `SuggestionChips`
- Actionable starter questions with improved hover/active/focus behavior.

7. `TracePanel`
- Expand/collapse tool calls with concise summary + detailed payload view.

### 3.2 Backend Adjustments

1. Keep backend behavior and contract unchanged.
2. Only perform compatibility/support edits if frontend refactor needs them.
3. No changes to tool-level policy behavior in this scope.

## 4. UI/UX Design Direction

### 4.1 Visual Style

1. Retain dark operational theme.
2. Add subtle layered background depth (gradient + low-noise feel).
3. Improve typography hierarchy and spacing rhythm for scanning.

### 4.2 Interaction Improvements

1. Lightweight enter animations for new messages (short, non-distracting).
2. Clear thinking/loading affordance.
3. Inline retry action after request failure.
4. Copy action for key response blocks where useful.

### 4.3 Input and Responsiveness

1. Auto-grow composer with max height cap.
2. Strong focus and disabled states.
3. Mobile-first spacing adjustments and preserved keyboard flows.

### 4.4 Trace and Warning Experience

1. Cleaner trace summary rows (tool, short result, state).
2. Better readability for args/result content.
3. Visual distinction between normal, warning, and error outcomes.

## 5. Implementation Plan (High-Level)

1. Frontend structure refactor:
- Introduce new components/hooks and move logic out of monolithic `App.tsx`.

2. Style and interaction pass:
- Upgrade layout, message rows, empty/loading/error states, trace panel.

3. Contract and compatibility checks:
- Ensure frontend API client remains aligned to backend response shape.

4. Test and verification pass:
- Run build/type checks and relevant unit/e2e tests.
- Fix regressions immediately.

## 6. Verification Strategy

### 6.1 Frontend

1. `npm run build` must pass.
2. Manual UX checks:
- suggestions -> send
- loading -> answer render
- warning banner visibility
- trace panel expand/collapse
- network failure and retry
- desktop/mobile layout sanity

### 6.2 Backend

1. Import/syntax checks for changed modules.
2. Parser and warning behavior tests remain passing.
3. No API schema regressions.

### 6.3 Test Scope

1. Targeted frontend interaction tests for new components/hook.
2. Existing backend parser/tool warning tests.
3. Broader test sweep where feasible in current environment.

## 7. Risks and Mitigations

1. Risk: UI refactor introduces state regressions.
- Mitigation: centralize state in `useChatSession`, add focused tests.

2. Risk: visual changes hurt readability.
- Mitigation: keep contrast and spacing high; verify mobile and keyboard behavior.

3. Risk: architecture drift with docs.
- Mitigation: update HLD/LLD references if module boundaries change.

## 8. Definition of Done for This Pass

1. UI is visibly more interactive and attractive.
2. Frontend code is split into clear components/hooks.
3. API contract remains unchanged and functional.
4. Changed-area checks/tests pass.
5. No new guardrail features introduced.

## 9. Self-Review Checklist (Completed)

1. Placeholder scan: no TBD/TODO placeholders left.
2. Consistency check: aligned with SPEC contract and approved scope.
3. Scope check: focused to one implementation cycle.
4. Ambiguity check: no competing interpretations for in-scope/out-of-scope boundaries.
