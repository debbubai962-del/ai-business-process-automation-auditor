"""Cache keys for expensive computations on the event log."""
from models.mapping import EventLog


def log_key(log: EventLog) -> tuple:
    return (log.cases, log.events, tuple(sorted(log.mapping.items())),
            str(log.df["timestamp"].min()), str(log.df["timestamp"].max()))