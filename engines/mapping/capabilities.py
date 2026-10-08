"""Tells the user which analyses the mapped data can support, and which it cannot."""
from models.mapping import Capability


def assess_capabilities(mapping: dict[str, str]) -> list[Capability]:
    has = lambda *keys: all(k in mapping for k in keys)
    core = has("case_id", "activity", "timestamp")
    out: list[Capability] = []

    def add(name, question, ok, need, limited_note=None):
        if ok:
            out.append(Capability(name, question, "available", "Supported by the mapped columns."))
        elif limited_note:
            out.append(Capability(name, question, "limited", limited_note))
        else:
            out.append(Capability(name, question, "unavailable", f"Needs: {need}."))

    add("Case cycle time", "How long does a case take end to end?", core, "case ID, step, start time")
    add("Step-level delay", "Where does time accumulate?", core, "case ID, step, start time")
    add("Rework detection", "How often do cases repeat a step?", core, "case ID, step, start time")
    add("Processing vs waiting time", "Is time spent working or waiting?", core and has("end_timestamp"),
        "end time",
        "Approximate only: no end time, so gaps between steps are used and labelled as approximate."
        if core else None)
    add("SLA compliance", "Are cases meeting their target?", core and has("sla"), "an SLA column",
        "Available if you enter a target manually in the simulator." if core else None)
    add("Department comparison", "Which department is slowest?", core and has("department"), "department")
    add("Team / employee analysis", "Who or which team drives delay?", core and has("resource"), "team or employee")
    add("Priority effect", "Does urgency change speed?", core and has("priority"), "priority")
    add("Value-at-risk", "How much money sits in delayed cases?", core and has("amount"), "amount or cost")
    add("Customer / vendor segments", "Do some segments cause friction?", core and has("customer"),
        "customer or vendor")
    return out