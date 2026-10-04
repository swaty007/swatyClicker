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
        return f"▶ работает ({status.fired})"
    if status.state == ActionState.PAUSED:
        return f"⏸ {status.reason}"
    if status.state == ActionState.ERROR:
        return f"⚠ {status.reason}"
    return "—"


def schedule_text(schedule) -> str:
    text = f"{schedule.interval:g} с"
    if schedule.jitter:
        text += f" ±{schedule.jitter:g}"
    return text
