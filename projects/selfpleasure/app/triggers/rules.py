"""Pure trigger configuration and evaluation foundation."""

from dataclasses import dataclass

from app.events import Event


@dataclass(frozen=True, slots=True)
class TriggerRule:
    event_topic: str
    minimum_confidence: float = 0.8


class TriggerEngine:
    def __init__(self, rules: tuple[TriggerRule, ...] = ()) -> None:
        self.rules = rules
        self.enabled = False

    def matches(self, event: Event) -> bool:
        if not self.enabled:
            return False
        confidence = float(event.payload.get("confidence", 0.0))
        return any(
            rule.event_topic == event.topic and confidence >= rule.minimum_confidence
            for rule in self.rules
        )

