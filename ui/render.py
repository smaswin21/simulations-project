"""
Rendering and event handling for the Pygame viewer.
"""

from __future__ import annotations

from pathlib import Path

from ui.world import AgentSpriteState, HUD_HEIGHT, TRAIL_LENGTH

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


def _draw_message_panel(screen, fonts: dict[str, object], recent_messages: list[dict], width: int, height: int):
    import pygame

    if not recent_messages:
        return

    panel_width = min(360, width - 24)
    line_height = 20
    panel_height = 16 + 22 + (line_height * len(recent_messages))
    panel_x = 12
    panel_y = height - panel_height - 12
    pygame.draw.rect(screen, PANEL_COLOR, (panel_x, panel_y, panel_width, panel_height), border_radius=8)
    pygame.draw.rect(screen, PANEL_BORDER, (panel_x, panel_y, panel_width, panel_height), 2, border_radius=8)

    title = fonts["main"].render("Recent Messages", True, TEXT_COLOR)
    screen.blit(title, (panel_x + 10, panel_y + 8))
    for index, message in enumerate(recent_messages):
        speaker = message.get("speaker") or "Unknown"
        content = message.get("text", "").replace("\n", " ").strip()
        if len(content) > 44:
            content = content[:41] + "..."
        text = fonts["small"].render(f"{speaker}: {content}", True, TEXT_COLOR)
        screen.blit(text, (panel_x + 10, panel_y + 34 + (index * line_height)))


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

        _draw_role_marker(screen, state, fonts, role_icons)

        if current_ticks <= state.speaking_until_ms:
            _draw_speech_bubble(screen, center[0], center[1] - 4)


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
    _draw_message_panel(screen, fonts, recent_messages, width, height)


def handle_events(controller, current_ticks: int) -> bool:
    import pygame

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type != pygame.KEYDOWN:
            continue
        if event.key == pygame.K_ESCAPE:
            return False
        if event.key == pygame.K_SPACE:
            controller.toggle_pause(current_ticks)
        elif event.key == pygame.K_RIGHT:
            controller.next_round(current_ticks)
        elif event.key == pygame.K_LEFT:
            controller.prev_round(current_ticks)
        elif event.key == pygame.K_r:
            controller.restart(current_ticks)
        elif event.key == pygame.K_t:
            controller.toggle_trails()
    return True
