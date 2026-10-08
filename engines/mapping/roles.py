"""The business roles a column can play in a process event log."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    required: bool
    help: str
    pattern: str          # regex on the column name
    kind: str             # text | datetime | numeric
    max_distinct: int = 0


ROLES = [
    Role("case_id", "Case / transaction ID", True,
         "One value per process instance, repeated on every step of that instance.",
         r"(case|ticket|order|claim|request|transaction|invoice|incident|application|job|item)[ _\-]?(id|no|num|number|ref|key)\b"
         r"|^id$|_id$|\bcase\b|\bticket\b|\bincident\b|\btransaction\b", "text"),
    Role("activity", "Process step / activity", True,
         "The step that was performed, such as Data Entry or Approval.",
         r"activity|activities|step|task|stage|event|action|operation", "text", 60),
    Role("timestamp", "Start time", True,
         "When the step started (or, if only one date exists, when it happened).",
         r"start|begin|creat|open|receiv|timestamp|time|date|logged|occur", "datetime"),
    Role("end_timestamp", "End time", False,
         "When the step finished. Enables processing time vs waiting time.",
         r"", "datetime"),
    Role("department", "Department", False,
         "The department responsible for the work.",
         r"dept|department|division|function|unit|business", "text", 100),
    Role("resource", "Team / employee", False,
         "Who performed the step.",
         r"team|employee|agent|user|resource|owner|assignee|assigned|worker|handler|analyst|operator|staff|person",
         "text", 500),
    Role("priority", "Priority", False,
         "Urgency of the case.", r"priorit|urgen|severity", "text", 10),
    Role("status", "Status", False,
         "Outcome or state of the step.", r"status|state|outcome|result", "text", 30),
    Role("sla", "SLA target (hours)", False,
         "Allowed end-to-end time for the case.", r"sla|target|deadline|allowed|threshold", "numeric"),
    Role("amount", "Amount / cost", False,
         "Monetary value of the case.", r"cost|amount|value|price|spend|charge|fee|total", "numeric"),
    Role("customer", "Customer / vendor", False,
         "The external party or segment.", r"customer|client|vendor|supplier|account|partner|counterpart",
         "text", 5000),
]
ROLE_BY_KEY = {r.key: r for r in ROLES}
END_PATTERN = r"(^|[\s_\-])(end|finish\w*|complet\w*|close\w*|stop|resolved|done)"