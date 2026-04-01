"""
Rendering and event handling for the Pygame viewer.
"""

from __future__ import annotations

import math
from pathlib import Path

from ui.world import AgentSpriteState, HUD_HEIGHT, TRAIL_LENGTH

MAX_PANEL_HEIGHT = 150

HUD_COLOR = (241, 236, 223)
HUD_BORDER_COLOR = (117, 107, 83)
TEXT_COLOR = (29, 28, 25)
PANEL_COLOR = (246, 242, 233)
PANEL_BORDER = (147, 134, 109)
COOPERATIVE_COLOR = (52, 163, 78)
AGGRESSIVE_COLOR = (198, 69, 58)
SPEECH_COLOR = (78, 127, 214)
TRAIL_DARKEN = 0.7
AGENT_RADIUS = 9
ROLE_BADGES = {
    "Herder": "H",
    "Regulator": "R",
    "Scout": "S",
}
ROLE_ICON_SIZE = 20
ROLE_ICON_OFFSET = (10, -18)
ROLE_ICON_PATHS = {
    "Herder": Path(__file__).resolve().parent / "assets" / "herder.png",
    "Regulator": Path(__file__).resolve().parent / "assets" / "regulator.png",
    "Scout": Path(__file__).resolve().parent / "assets" / "scout.png",
}


def load_role_icons():
    import pygame

    role_icons = {}
    for role, path in ROLE_ICON_PATHS.items():
        try:
            surface = pygame.image.load(str(path)).convert_alpha()
            role_icons[role] = pygame.transform.smoothscale(
                surface,
                (ROLE_ICON_SIZE, ROLE_ICON_SIZE),
            )
        except Exception:
            role_icons[role] = None
    return role_icons


def get_agent_body_color(agent_state: AgentSpriteState) -> tuple[int, int, int]:
    return AGGRESSIVE_COLOR if agent_state.grazed > 1 else COOPERATIVE_COLOR


def _darken(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)


def _draw_hud(screen, fonts: dict[str, object], round_data: dict, width: int, paused: bool):
    import pygame

    pygame.draw.rect(screen, HUD_COLOR, (0, 0, width, HUD_HEIGHT))
    pygame.draw.line(screen, HUD_BORDER_COLOR, (0, HUD_HEIGHT - 1), (width, HUD_HEIGHT - 1), 2)

    main_font = fonts["main"]
    small_font = fonts["small"]
    status = "Paused" if paused else "Playing"
    texts = [
        main_font.render(f"Round: {round_data['round']}", True, TEXT_COLOR),
        main_font.render(f"Stock: {round_data['stock']}", True, TEXT_COLOR),
        main_font.render(f"Total Grazed: {round_data['total_grazed']}", True, TEXT_COLOR),
        main_font.render(f"Coop Rate: {round_data.get('coop_rate', 1.0) * 100:.1f}%", True, TEXT_COLOR),
        main_font.render(status, True, TEXT_COLOR),
    ]
    positions = [(16, 12), (150, 12), (275, 12), (490, 12), (740, 12)]
    for text, pos in zip(texts, positions):
        screen.blit(text, pos)

    hints = "Space play/pause  Left/Right step  R restart  T trails  Esc quit"
    hint_text = small_font.render(hints, True, TEXT_COLOR)
    screen.blit(hint_text, (16, 48))


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word  # oversized single word emitted as-is
    if current:
        lines.append(current)
    return lines if lines else [""]


def _draw_message_panel(
    screen,
    fonts: dict[str, object],
    recent_messages: list[dict],
    width: int,
    height: int,
    scroll_offset: int = 0,
):
    import pygame

    if not recent_messages:
        return

    small_font = fonts["small"]
    panel_width = min(360, width - 24)
    wrap_width = panel_width - 20
    line_height = 20
    lines_that_fit = MAX_PANEL_HEIGHT // line_height

    all_lines: list[str] = []
    for message in recent_messages:
        speaker = message.get("speaker") or "Unknown"
        content = message.get("text", "").replace("\n", " ").strip()
        all_lines.extend(_wrap_text(f"{speaker}: {content}", small_font, wrap_width))

    total_lines = len(all_lines)
    max_offset = max(0, total_lines - lines_that_fit)
    scroll_offset = max(0, min(scroll_offset, max_offset))
    visible_lines = all_lines[scroll_offset: scroll_offset + lines_that_fit]

    title_area = 16 + 22
    panel_height = min(title_area + total_lines * line_height, title_area + MAX_PANEL_HEIGHT)
    panel_x = 12
    panel_y = height - panel_height - 12

    pygame.draw.rect(screen, PANEL_COLOR, (panel_x, panel_y, panel_width, panel_height), border_radius=8)
    pygame.draw.rect(screen, PANEL_BORDER, (panel_x, panel_y, panel_width, panel_height), 2, border_radius=8)

    title = fonts["main"].render("Recent Messages", True, TEXT_COLOR)
    screen.blit(title, (panel_x + 10, panel_y + 8))

    for i, line in enumerate(visible_lines):
        text = small_font.render(line, True, TEXT_COLOR)
        screen.blit(text, (panel_x + 10, panel_y + title_area + i * line_height))

    if total_lines > lines_that_fit:
        bar_x = panel_x + panel_width - 6
        bar_h = panel_height - title_area - 4
        thumb_h = max(12, int(bar_h * lines_that_fit / total_lines))
        thumb_y = panel_y + title_area + int((bar_h - thumb_h) * (scroll_offset / max_offset))
        pygame.draw.rect(screen, PANEL_BORDER, (bar_x, panel_y + title_area, 4, bar_h), border_radius=2)
        pygame.draw.rect(screen, TEXT_COLOR, (bar_x, thumb_y, 4, thumb_h), border_radius=2)


def _draw_trails(screen, agent_states: dict[int, AgentSpriteState]):
    import pygame

    for state in agent_states.values():
        if len(state.trail) < 2:
            continue
        color = _darken(get_agent_body_color(state), TRAIL_DARKEN)
        points = [(int(x), int(y)) for x, y in state.trail]
        pygame.draw.lines(screen, color, False, points, 2)


def _draw_speech_bubble(screen, x: int, y: int):
    import pygame

    bubble_rect = pygame.Rect(x - 11, y - 32, 22, 14)
    pygame.draw.ellipse(screen, (239, 246, 255), bubble_rect)
    pygame.draw.ellipse(screen, SPEECH_COLOR, bubble_rect, 2)
    tail = [(x - 2, y - 18), (x + 3, y - 18), (x, y - 12)]
    pygame.draw.polygon(screen, (239, 246, 255), tail)
    pygame.draw.lines(screen, SPEECH_COLOR, False, [tail[0], tail[2], tail[1]], 2)


def _draw_role_marker(screen, state: AgentSpriteState, fonts: dict[str, object], role_icons: dict[str, object]):
    icon = role_icons.get(state.role)
    if icon is not None:
        x = int(state.x) + ROLE_ICON_OFFSET[0]
        y = int(state.y) + ROLE_ICON_OFFSET[1]
        screen.blit(icon, (x, y))
        return

    badge_font = fonts["small"]
    badge = ROLE_BADGES.get(state.role, "?")
    badge_label = badge_font.render(badge, True, TEXT_COLOR)
    screen.blit(badge_label, (int(state.x) + ROLE_ICON_OFFSET[0], int(state.y) + ROLE_ICON_OFFSET[1]))


def _draw_agents(
    screen,
    fonts: dict[str, object],
    agent_states: dict[int, AgentSpriteState],
    current_ticks: int,
    role_icons: dict[str, object],
):
    import pygame

    id_font = fonts["tiny"]

    for state in sorted(agent_states.values(), key=lambda item: item.agent_id):
        center = (int(state.x), int(state.y))
        pygame.draw.circle(screen, get_agent_body_color(state), center, AGENT_RADIUS)
        pygame.draw.circle(screen, TEXT_COLOR, center, AGENT_RADIUS, 2)

        id_label = id_font.render(str(state.agent_id), True, TEXT_COLOR)
        screen.blit(id_label, id_label.get_rect(center=center))

        name_x = int(state.x) + AGENT_RADIUS + 4
        name_y = int(state.y) - 6
        shadow = id_font.render(state.name, True, (240, 240, 240))
        screen.blit(shadow, (name_x + 1, name_y + 1))
        name_label = id_font.render(state.name, True, TEXT_COLOR)
        screen.blit(name_label, (name_x, name_y))

        _draw_role_marker(screen, state, fonts, role_icons)

        if current_ticks <= state.speaking_until_ms:
            _draw_speech_bubble(screen, center[0], center[1] - 4)


def _draw_agent_popup(
    screen,
    fonts: dict[str, object],
    state: AgentSpriteState,
    total_grazed: int,
    last_message: str | None,
    width: int,
    height: int,
) -> None:
    import pygame

    from ui.world import HUD_HEIGHT

    POPUP_WIDTH = 200
    PADDING = 10
    line_height = 20
    small_font = fonts["small"]
    main_font = fonts["main"]

    msg_text = last_message if last_message is not None else "(no messages yet)"
    msg_color = TEXT_COLOR if last_message is not None else (140, 130, 110)
    msg_lines = _wrap_text(msg_text, small_font, POPUP_WIDTH - PADDING * 2)[:3]

    popup_height = PADDING + 26 + line_height + 4 + len(msg_lines) * line_height + PADDING

    cx = int(state.x)
    cy = int(state.y)
    popup_x = max(4, min(cx - POPUP_WIDTH // 2, width - POPUP_WIDTH - 4))
    popup_y = cy - AGENT_RADIUS - popup_height - 8
    if popup_y < HUD_HEIGHT + 4:
        popup_y = cy + AGENT_RADIUS + 8

    rect = pygame.Rect(popup_x, popup_y, POPUP_WIDTH, popup_height)
    pygame.draw.rect(screen, PANEL_COLOR, rect, border_radius=6)
    pygame.draw.rect(screen, PANEL_BORDER, rect, 2, border_radius=6)

    y = popup_y + PADDING
    header = main_font.render(f"{state.name}  [{state.role}]", True, TEXT_COLOR)
    screen.blit(header, (popup_x + PADDING, y))
    y += 26
    grazed_surf = small_font.render(f"Grazed: {total_grazed} rounds", True, TEXT_COLOR)
    screen.blit(grazed_surf, (popup_x + PADDING, y))
    y += line_height + 4
    pygame.draw.line(screen, PANEL_BORDER, (popup_x + PADDING, y), (popup_x + POPUP_WIDTH - PADDING, y))
    y += 4
    for line in msg_lines:
        line_surf = small_font.render(line, True, msg_color)
        screen.blit(line_surf, (popup_x + PADDING, y))
        y += line_height


def draw_frame(
    screen,
    background_surface,
    round_data: dict,
    agent_states: dict[int, AgentSpriteState],
    recent_messages: list[dict],
    width: int,
    height: int,
    *,
    role_icons: dict[str, object],
    paused: bool,
    show_trails: bool,
    current_ticks: int,
    scroll_offset: int = 0,
    selected_agent_id: int | None = None,
    agent_total_grazed: int = 0,
    agent_last_message: str | None = None,
) -> None:
    import pygame

    fonts = {
        "main": pygame.font.SysFont(None, 26),
        "small": pygame.font.SysFont(None, 20),
        "tiny": pygame.font.SysFont(None, 18),
    }

    screen.blit(background_surface, (0, 0))
    if show_trails:
        _draw_trails(screen, agent_states)
    _draw_agents(screen, fonts, agent_states, current_ticks, role_icons)
    _draw_hud(screen, fonts, round_data, width, paused)
    _draw_message_panel(screen, fonts, recent_messages, width, height, scroll_offset)
    if selected_agent_id is not None and selected_agent_id in agent_states:
        _draw_agent_popup(
            screen, fonts, agent_states[selected_agent_id],
            agent_total_grazed, agent_last_message, width, height,
        )


def handle_events(controller, current_ticks: int, agent_states: dict | None = None) -> bool:
    import pygame

    agent_states = agent_states or {}

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            elif event.key == pygame.K_SPACE:
                controller.toggle_pause(current_ticks)
            elif event.key == pygame.K_RIGHT:
                controller.next_round(current_ticks)
            elif event.key == pygame.K_LEFT:
                controller.prev_round(current_ticks)
            elif event.key == pygame.K_r:
                controller.restart(current_ticks)
            elif event.key == pygame.K_t:
                controller.toggle_trails()
        elif event.type == pygame.MOUSEWHEEL:
            controller.message_scroll_offset -= event.y
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = False
            for state in agent_states.values():
                if math.hypot(event.pos[0] - state.x, event.pos[1] - state.y) <= AGENT_RADIUS + 4:
                    controller.selected_agent_id = state.agent_id
                    hit = True
                    break
            if not hit:
                controller.selected_agent_id = None
    return True
