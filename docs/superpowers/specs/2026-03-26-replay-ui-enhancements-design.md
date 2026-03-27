# Replay UI Enhancements — Design Spec

**Date:** 2026-03-26
**Status:** Approved
**Scope:** `ui/render.py`, `ui/world.py`, `ui/replay.py`, `ui/pygame_app.py`

---

## Context

The replay viewer shows pre-recorded simulation runs using Pygame. Three usability gaps were identified:

1. Agent circles show only a numeric ID — no name, making it hard to correlate agents with their messages.
2. The messages panel truncates text at 44 chars and shows only 5 messages — not enough to follow a conversation.
3. There is no way to inspect an individual agent's details (name, role, rounds grazed, last message) without cross-referencing the HUD and message panel manually.

---

## Feature 1 — Agent Name Labels

### What
Render each agent's name as a small text label always visible beside the agent circle.

### How
- In `_draw_agents()` in `render.py`, after drawing the agent ID number, render the agent name using `fonts["tiny"]` (SysFont 18).
- The name comes from `AgentSpriteState.name` (new field, see world.py changes below).
- Position: `(int(state.x) + AGENT_RADIUS + 4, int(state.y) - 6)` — to the right of the circle, vertically centred.
- Use a simple drop-shadow for legibility: render name in `(240, 240, 240)` offset by `(+1, +1)`, then render name in `TEXT_COLOR` on top at the original position.

### Data changes — `world.py`
- Add `name: str = ""` field to `AgentSpriteState` dataclass.
- Populate it in `init_agent_states()` from `agent.get("name", f"Agent {agent['id']}")` (fallback keeps labels meaningful if the field is absent).
- Keep it synced in `apply_round_state()` from `agent.get("name", state.name)`.

---

## Feature 2 — Scrollable Messages Panel

### What
Make the messages panel taller and scrollable. Show full message text (no truncation). Increase message limit to 10.

### Constants / data changes
- Raise `MESSAGE_LIMIT` from `5` to `10` in `replay.py`.
- Add `message_scroll_offset: int = 0` field to `ReplayController` in `replay.py`.
- Reset `message_scroll_offset = 0` on round transitions:
  - In `next_round()`, `prev_round()`, and `restart()`: reset unconditionally before returning.
  - In `update()`: reset **only on the path that actually advances a round** — i.e., immediately before `return True`, not on the early-return paths (paused / already at last round). Resetting unconditionally every call would break scrolling since `update()` is called every frame.
- Add `MAX_PANEL_HEIGHT: int = 200` as a module-level constant in `render.py`.

### Rendering — `_draw_message_panel()` in `render.py`
- Remove the 44-char truncation (`content[:41] + "..."` logic).
- Add `_wrap_text(text: str, font, max_width: int) -> list[str]` helper in `render.py`. Greedy word-wrap using `font.size(word)` to accumulate words until a line overflows, then starts a new line.
- For each message, produce wrapped lines and collect all lines across all messages into a flat list.
- `line_height = 20`. `lines_that_fit = MAX_PANEL_HEIGHT // line_height`.
- `_draw_message_panel()` gains a new parameter: `scroll_offset: int`.
- `draw_frame()` passes `controller.message_scroll_offset` through to `_draw_message_panel()` as `scroll_offset`.
- Inside `_draw_message_panel()`: `max_offset = max(0, total_lines - lines_that_fit)`. Clamp the received `scroll_offset` to `[0, max_offset]` before rendering.
- Render only lines `[scroll_offset : scroll_offset + lines_that_fit]`.
- Panel height = `min(16 + 22 + total_lines * line_height, MAX_PANEL_HEIGHT + 16 + 22)`.
- Show a faint scrollbar indicator (4px-wide rect on the right inner edge of the panel) when `total_lines > lines_that_fit`. Scrollbar thumb height proportional to `lines_that_fit / total_lines`; thumb Y offset proportional to `scroll_offset / max_offset`.

### Event handling — `handle_events()` in `render.py`
- **The current `if event.type != pygame.KEYDOWN: continue` guard must be replaced** with a multi-branch `if/elif` dispatch so that `MOUSEBUTTONDOWN` and `MOUSEWHEEL` events are reachable.
- New structure:
  ```python
  for event in pygame.event.get():
      if event.type == pygame.QUIT:
          return False
      elif event.type == pygame.KEYDOWN:
          # existing key handling
      elif event.type == pygame.MOUSEWHEEL:
          controller.message_scroll_offset -= event.y  # scroll up = negative y in pygame
          # clamping happens in _draw_message_panel at render time
      elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          # Feature 3 click handling (see below)
  ```

---

## Feature 3 — Agent Click Popup

### What
Click an agent → floating popup appears above it showing: name, role, cumulative rounds grazed (across all rounds up to current), and last spoken message in full. Click elsewhere to dismiss.

### Data changes — `replay.py`
- Add `selected_agent_id: int | None = None` field to `ReplayController`. Do **not** reset on round advance — selection persists across rounds so the user can watch one agent.
- Add `get_agent_total_grazed(agent_id: int) -> int`: iterates `self.rounds[:self.current_index + 1]`, sums `agent.get("grazed", 0)` for agents whose `agent["id"] == agent_id` (uses `.get` defensively, consistent with `apply_round_state()`).
- Add `get_agent_last_message(agent_id: int) -> str | None`: scans `self.rounds[:self.current_index + 1]` messages in reverse, returns `msg["text"]` for the first `msg` where `msg["agent_id"] == agent_id` **and `msg["agent_id"] is not None`** (guards against unresolved name→id lookups in `load_replay_rounds()`).

### Click detection — `handle_events()` in `render.py`
- `handle_events()` gains a new parameter: `agent_states: dict[int, AgentSpriteState]`.
- Updated call signature in `pygame_app.py`: `handle_events(controller, current_ticks, agent_states)`.
- On `MOUSEBUTTONDOWN` (button 1):
  - Iterate `agent_states.values()`. For each, check `math.hypot(event.pos[0] - state.x, event.pos[1] - state.y) <= AGENT_RADIUS + 4`.
  - If hit: `controller.selected_agent_id = state.agent_id`.
  - If no hit: `controller.selected_agent_id = None`.
- Add `import math` at top of `render.py`.

### Drawing — `_draw_agent_popup()` in `render.py`
Signature: `_draw_agent_popup(screen, fonts, state, total_grazed, last_message, width, height)`

- Panel width: 200px.
- Contents (10px internal padding):
  - `fonts["main"]` — `f"{state.name}  [{state.role}]"`
  - `fonts["small"]` — `f"Grazed: {total_grazed} rounds"`
  - Horizontal divider line in `PANEL_BORDER` colour
  - `fonts["small"]` — last message text, word-wrapped to panel width - 20px, max 3 lines. If `last_message` is None, show `"(no messages yet)"` in a muted colour.
- Panel height: computed from content lines.
- Position:
  - X: centred on `state.x`, clamped so popup stays within `[4, width - panel_width - 4]`.
  - Y: top of popup = `int(state.y) - AGENT_RADIUS - popup_height - 8`, clamped so top Y ≥ `HUD_HEIGHT + 4` (prevents drawing over the HUD). If popup would go above HUD, flip it below the agent: `int(state.y) + AGENT_RADIUS + 8`.
- Draw: `PANEL_COLOR` fill + `PANEL_BORDER` 2px outline, `border_radius=6` — matching existing panel style.

### Wiring — `draw_frame()` in `render.py`
- Add three new keyword-only parameters: `selected_agent_id: int | None`, `agent_total_grazed: int`, `agent_last_message: str | None`.
- At the end of `draw_frame()`, after `_draw_message_panel()`, call:
  ```python
  if selected_agent_id is not None and selected_agent_id in agent_states:
      _draw_agent_popup(screen, fonts, agent_states[selected_agent_id],
                        agent_total_grazed, agent_last_message, width, height)
  ```
  The popup is drawn last so it appears on top of the message panel if they overlap.

### Wiring — `run_viewer()` in `pygame_app.py`
- Compute popup data before calling `draw_frame()`:
  ```python
  sel = controller.selected_agent_id
  total_grazed = controller.get_agent_total_grazed(sel) if sel is not None else 0
  last_msg = controller.get_agent_last_message(sel) if sel is not None else None
  ```
- Pass to `draw_frame()` as keyword args: `selected_agent_id=sel`, `agent_total_grazed=total_grazed`, `agent_last_message=last_msg`.

---

## Files Modified

| File | Changes |
|------|---------|
| `ui/world.py` | Add `name: str = ""` to `AgentSpriteState`; populate/sync in `init_agent_states` and `apply_round_state` |
| `ui/replay.py` | Raise `MESSAGE_LIMIT` to 10; add `selected_agent_id`, `message_scroll_offset` to `ReplayController`; reset `message_scroll_offset` in all four mutators; add `get_agent_total_grazed()`, `get_agent_last_message()` |
| `ui/render.py` | `_wrap_text()` helper; `MAX_PANEL_HEIGHT` constant; Feature 1 name label in `_draw_agents`; Feature 2 word-wrap + scroll + scrollbar in `_draw_message_panel`; restructure `handle_events()` event loop; Feature 3 `_draw_agent_popup()`; updated `draw_frame()` signature; `import math` |
| `ui/pygame_app.py` | Pass `agent_states` to `handle_events()`; compute and pass popup data to `draw_frame()` |

---

## Verification

1. Run `python -m ui.pygame_app --simulation-id <any_valid_id>`
2. Agent names appear beside each circle (drop-shadow readable on both grass and tan tiles).
3. Message panel shows full text, up to 10 messages, scrolls with mouse wheel.
4. Click an agent → popup appears above it (or below if near HUD) with name, role, cumulative grazed count, and last message.
5. Click elsewhere → popup dismisses.
6. Step forward/back through rounds — popup stays on selected agent, grazed count and last message update; message scroll resets to 0.
7. Agents near the top of the world area: popup flips below rather than overlapping the HUD.
