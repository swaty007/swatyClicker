"""Human-readable texts for domain values shown in the UI."""
from myclicker.domain.compatibility import Status
from myclicker.domain.engine import ActionState, ActionStatus
from myclicker.domain.model import MouseButton

BUTTONS = {MouseButton.LEFT: "Левая", MouseButton.RIGHT: "Правая", MouseButton.MIDDLE: "Средняя"}
BUTTONS_BY_TEXT = {text: button for button, text in BUTTONS.items()}

COMPAT = {
    Status.WORKS: "✅ работает",
    Status.PARTIAL: "⚠ частично",
    Status.FAILS: "❌ не работает",
    Status.UNTESTED: "— не проверялось",
}


def status_text(status: ActionStatus, enabled: bool = True) -> str:
    if not enabled:
        return "выключено"
    if status.state == ActionState.RUNNING:
        text = f"▶ работает ({status.fired})"
    elif status.state == ActionState.PAUSED:
        text = f"⏸ {status.reason}"
    elif status.state == ActionState.ERROR:
        text = f"⚠ {status.reason}"
    else:
        return "—"
    if status.moves:
        dx, dy = status.last_shift
        text += f" · сдвиг {status.moves}× ({dx:+d}, {dy:+d})"
    return text


def schedule_text(schedule) -> str:
    text = f"{schedule.interval:g} с"
    if schedule.jitter:
        text += f" ±{schedule.jitter:g}"
    return text
