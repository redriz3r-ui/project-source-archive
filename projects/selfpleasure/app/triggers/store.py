"""Local rule presets; only one supported, enabled automation rule at a time."""

from dataclasses import asdict, dataclass, replace
import json
import math
import os
from pathlib import Path
from uuid import uuid4

from app.triggers.automation import AutomationRule
from app.triggers.patterns import Pattern
from app.paths import private_data_path


DEFAULT_PATH = private_data_path("config.local.rules.json")


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    id: str
    name: str
    enabled: bool
    trigger: str
    action: str
    pattern: str
    feature_index: int
    intensity: float
    duration: float
    cooldown: float
    minimum_confidence: float

    def automation_rule(self) -> AutomationRule:
        return AutomationRule(
            feature_index=self.feature_index, intensity=self.intensity,
            duration=self.duration, cooldown=self.cooldown,
            minimum_confidence=self.minimum_confidence, pattern=Pattern(self.pattern),
        )


class RuleStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        self._rules: dict[str, RuleDefinition] = {}
        self.load_error: str | None = None
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    raise ValueError("Expected a list of rules")
                for item in data:
                    rule = RuleDefinition(**item)
                    self._validate(rule)
                    self._rules[rule.id] = rule
                if sum(rule.enabled for rule in self._rules.values()) > 1:
                    raise ValueError("Multiple enabled rules")
            except (OSError, ValueError, TypeError) as exc:
                self._rules.clear()
                self.load_error = f"Local rule configuration could not be loaded: {exc}"

    @staticmethod
    def _validate(rule: RuleDefinition) -> None:
        if not 1 <= len(rule.name.strip()) <= 64:
            raise ValueError("Rule name must contain 1–64 characters")
        if (rule.trigger, rule.action) != ("INTERACTION_ACTIVE", "VIBRATE"):
            raise ValueError("Only Interaction Active → Vibrate is supported")
        if rule.pattern not in {pattern.value for pattern in Pattern}:
            raise ValueError("Unsupported vibration pattern")
        if not isinstance(rule.feature_index, int) or rule.feature_index < 0:
            raise ValueError("Choose a valid vibration feature")
        values = (rule.intensity, rule.duration, rule.cooldown, rule.minimum_confidence)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Rule values must be finite")
        if not (0 < rule.intensity <= 0.5 and 0 < rule.duration <= 2.0
                and 0.5 <= rule.cooldown <= 30 and 0 <= rule.minimum_confidence <= 1):
            raise ValueError("Rule values exceed conservative limits")

    def list(self) -> list[dict[str, object]]:
        return [asdict(rule) for rule in self._rules.values()]

    def get(self, identifier: str) -> RuleDefinition | None:
        return self._rules.get(identifier)

    def enabled(self) -> RuleDefinition | None:
        return next((rule for rule in self._rules.values() if rule.enabled), None)

    def create(self, **fields: object) -> RuleDefinition:
        self._assert_writable()
        rule = RuleDefinition(id=uuid4().hex, enabled=False, **fields)
        self._validate(rule)
        before = self._rules.copy()
        self._rules[rule.id] = rule
        try:
            self._save()
        except OSError:
            self._rules = before
            raise
        return rule

    def update(self, identifier: str, **fields: object) -> RuleDefinition:
        self._assert_writable()
        current = self._rules.get(identifier)
        if current is None:
            raise KeyError(identifier)
        rule = replace(current, **fields)
        self._validate(rule)
        before = self._rules.copy()
        self._rules[identifier] = rule
        try:
            self._save()
        except OSError:
            self._rules = before
            raise
        return rule

    def set_enabled(self, identifier: str, enabled: bool) -> RuleDefinition:
        self._assert_writable()
        if identifier not in self._rules:
            raise KeyError(identifier)
        before = self._rules.copy()
        if enabled:
            self._rules = {key: replace(rule, enabled=(key == identifier))
                           for key, rule in self._rules.items()}
        else:
            self._rules[identifier] = replace(self._rules[identifier], enabled=False)
        try:
            self._save()
        except OSError:
            self._rules = before
            raise
        return self._rules[identifier]

    def delete(self, identifier: str) -> None:
        self._assert_writable()
        if identifier not in self._rules:
            raise KeyError(identifier)
        before = self._rules.copy()
        del self._rules[identifier]
        try:
            self._save()
        except OSError:
            self._rules = before
            raise

    def _assert_writable(self) -> None:
        if self.load_error is not None:
            raise RuntimeError("Repair the invalid local rule file before changing rules")

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(self.list(), indent=2) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, self.path)
            self.load_error = None
        finally:
            temporary.unlink(missing_ok=True)
