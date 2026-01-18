from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Union, Optional
from uuid import uuid4
import json


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class ActionType(str, Enum):
    CREDIT_REWARD = "credit_reward"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_STATUS = "update_status"
    TRIGGER_WEBHOOK = "trigger_webhook"


class TriggerEvent(str, Enum):
    REFERRAL_SIGNUP = "referral_signup"
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    PAYMENT_RECEIVED = "payment_received"
    MANUAL = "manual"


@dataclass
class Condition:
    field: str
    operator: ConditionOperator
    value: Any = None
    
    def evaluate(self, context: dict) -> bool:
        field_value = self._get_field_value(context, self.field)
        return self._apply_operator(field_value, self.value)
    
    def _get_field_value(self, context: dict, field_path: str) -> Any:
        parts = field_path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def _apply_operator(self, field_value: Any, compare_value: Any) -> bool:
        op = self.operator
        if op == ConditionOperator.EQUALS: return field_value == compare_value
        if op == ConditionOperator.NOT_EQUALS: return field_value != compare_value
        if op == ConditionOperator.GREATER_THAN: return field_value > compare_value
        if op == ConditionOperator.LESS_THAN: return field_value < compare_value
        if op == ConditionOperator.GREATER_THAN_OR_EQUAL: return field_value >= compare_value
        if op == ConditionOperator.LESS_THAN_OR_EQUAL: return field_value <= compare_value
        if op == ConditionOperator.CONTAINS: return compare_value in field_value if field_value else False
        if op == ConditionOperator.NOT_CONTAINS: return compare_value not in field_value if field_value else True
        if op == ConditionOperator.IN: return field_value in compare_value if compare_value else False
        if op == ConditionOperator.NOT_IN: return field_value not in compare_value if compare_value else True
        if op == ConditionOperator.IS_TRUE: return bool(field_value) is True
        if op == ConditionOperator.IS_FALSE: return bool(field_value) is False
        return False
    
    def to_dict(self) -> dict:
        return {"field": self.field, "operator": self.operator.value, "value": self.value}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Condition":
        return cls(field=data["field"], operator=ConditionOperator(data["operator"]), value=data.get("value"))


@dataclass
class ConditionGroup:
    operator: LogicalOperator
    conditions: list[Union[Condition, "ConditionGroup"]]
    
    def evaluate(self, context: dict) -> bool:
        if not self.conditions:
            return True
        results = [cond.evaluate(context) for cond in self.conditions]
        return all(results) if self.operator == LogicalOperator.AND else any(results)
    
    def to_dict(self) -> dict:
        return {"operator": self.operator.value, "conditions": [c.to_dict() for c in self.conditions]}
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConditionGroup":
        conditions = []
        for c in data["conditions"]:
            if "operator" in c and "conditions" in c:
                conditions.append(ConditionGroup.from_dict(c))
            else:
                conditions.append(Condition.from_dict(c))
        return cls(operator=LogicalOperator(data["operator"]), conditions=conditions)


@dataclass
class Action:
    type: ActionType
    params: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {"type": self.type.value, "params": self.params}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(type=ActionType(data["type"]), params=data.get("params", {}))


@dataclass
class Rule:
    id: str
    name: str
    trigger: TriggerEvent
    conditions: Union[Condition, ConditionGroup]
    actions: list[Action]
    description: str = ""
    version: int = 1
    is_active: bool = True
    priority: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def evaluate(self, context: dict) -> bool:
        if not self.is_active:
            return False
        return self.conditions.evaluate(context)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "version": self.version, "is_active": self.is_active, "priority": self.priority,
            "trigger": self.trigger.value, "conditions": self.conditions.to_dict(),
            "actions": [a.to_dict() for a in self.actions], "metadata": self.metadata
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        cond_data = data["conditions"]
        conditions = ConditionGroup.from_dict(cond_data) if "operator" in cond_data and "conditions" in cond_data else Condition.from_dict(cond_data)
        actions = [Action.from_dict(a) for a in data["actions"]]
        return cls(
            id=data["id"], name=data["name"], description=data.get("description", ""),
            version=data.get("version", 1), is_active=data.get("is_active", True),
            priority=data.get("priority", 0), trigger=TriggerEvent(data["trigger"]),
            conditions=conditions, actions=actions, metadata=data.get("metadata", {})
        )


class RuleEngine:
    def __init__(self):
        self.rules: dict[str, Rule] = {}
        self.action_handlers: dict[ActionType, callable] = {
            ActionType.CREDIT_REWARD: self._handle_credit_reward,
            ActionType.SEND_NOTIFICATION: self._handle_send_notification,
            ActionType.UPDATE_STATUS: self._handle_update_status,
            ActionType.TRIGGER_WEBHOOK: self._handle_trigger_webhook,
        }
    
    def add_rule(self, rule: Rule) -> None:
        self.rules[rule.id] = rule
    
    def remove_rule(self, rule_id: str) -> None:
        self.rules.pop(rule_id, None)
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self.rules.get(rule_id)
    
    def list_rules(self, trigger: Optional[TriggerEvent] = None) -> list[Rule]:
        rules = list(self.rules.values())
        if trigger:
            rules = [r for r in rules if r.trigger == trigger]
        rules.sort(key=lambda r: r.priority, reverse=True)
        return rules
    
    def evaluate(self, trigger: TriggerEvent, context: dict) -> list[Rule]:
        return [rule for rule in self.list_rules(trigger) if rule.evaluate(context)]
    
    def execute(self, trigger: TriggerEvent, context: dict) -> list[dict]:
        results = []
        for rule in self.evaluate(trigger, context):
            rule_result = {"rule_id": rule.id, "rule_name": rule.name, "actions_executed": []}
            for action in rule.actions:
                handler = self.action_handlers.get(action.type)
                if handler:
                    try:
                        action_result = handler(action.params, context)
                        rule_result["actions_executed"].append({"type": action.type.value, "success": True, "result": action_result})
                    except Exception as e:
                        rule_result["actions_executed"].append({"type": action.type.value, "success": False, "error": str(e)})
            results.append(rule_result)
        return results
    
    def _handle_credit_reward(self, params: dict, context: dict) -> dict:
        return {"action": "credit_reward", "amount": params.get("amount"), "currency": params.get("currency", "INR"), "status": "created"}
    
    def _handle_send_notification(self, params: dict, context: dict) -> dict:
        return {"action": "send_notification", "channel": params.get("channel", "email"), "status": "sent"}
    
    def _handle_update_status(self, params: dict, context: dict) -> dict:
        return {"action": "update_status", "new_status": params.get("status"), "status": "updated"}
    
    def _handle_trigger_webhook(self, params: dict, context: dict) -> dict:
        return {"action": "trigger_webhook", "url": params.get("url"), "status": "triggered"}


def create_sample_rules() -> list[Rule]:
    return [
        Rule(
            id="rule-premium-referral", name="Premium Referral Reward",
            trigger=TriggerEvent.SUBSCRIPTION_STARTED,
            conditions=ConditionGroup(operator=LogicalOperator.AND, conditions=[
                Condition(field="referrer.is_paid_user", operator=ConditionOperator.EQUALS, value=True),
                Condition(field="referred.subscription_plan", operator=ConditionOperator.EQUALS, value="premium")
            ]),
            actions=[
                Action(type=ActionType.CREDIT_REWARD, params={"amount": 500, "currency": "INR", "reward_type": "voucher"}),
                Action(type=ActionType.SEND_NOTIFICATION, params={"channel": "email", "template": "reward_credited"})
            ],
            priority=10
        ),
        Rule(
            id="rule-signup-bonus", name="Signup Bonus",
            trigger=TriggerEvent.REFERRAL_SIGNUP,
            conditions=Condition(field="referred.signup_completed", operator=ConditionOperator.IS_TRUE),
            actions=[Action(type=ActionType.CREDIT_REWARD, params={"amount": 100, "currency": "INR", "reward_type": "voucher"})],
            priority=5
        ),
    ]


if __name__ == "__main__":
    engine = RuleEngine()
    for rule in create_sample_rules():
        engine.add_rule(rule)
        print(f"Added rule: {rule.name}")
    
    context = {"referrer": {"id": "user-123", "is_paid_user": True}, "referred": {"subscription_plan": "premium"}}
    results = engine.execute(TriggerEvent.SUBSCRIPTION_STARTED, context)
    print("Results:", json.dumps(results, indent=2))
