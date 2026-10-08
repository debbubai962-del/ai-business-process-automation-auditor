"""Workflow stepper: always answers 'Where am I?'"""
from ui.components.html import render


def render_stepper(steps: list[str], current: int, completed: set[int] | None = None) -> None:
    completed = completed or set()
    items = ""
    for i, name in enumerate(steps):
        if i == current:
            state, mark = "active", str(i + 1)
        elif i in completed:
            state, mark = "done", "&#10003;"
        else:
            state, mark = "todo", str(i + 1)
        items += f'<div class="step {state}"><div class="step-dot">{mark}</div><div class="step-label">{name}</div></div>'
    render(f'<div class="stepper">{items}</div>')