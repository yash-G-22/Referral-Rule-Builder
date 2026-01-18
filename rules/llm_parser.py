import json
import os
import re
from typing import Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

SYSTEM_PROMPT = """You are a rule generator for a referral management system.
Convert the user's natural language description into a structured JSON rule.

The JSON rule must follow this schema:
{
    "id": "unique-rule-id",
    "name": "Human readable name",
    "description": "Full description",
    "trigger": "one of: referral_signup, subscription_started, subscription_cancelled, payment_received, manual",
    "conditions": {
        "operator": "AND or OR",
        "conditions": [
            {"field": "field.path", "operator": "equals/greater_than/is_true", "value": "value"}
        ]
    },
    "actions": [
        {"type": "credit_reward", "params": {"amount": number, "currency": "INR", "reward_type": "voucher"}}
    ]
}

Available fields: referrer.is_paid_user, referrer.tier, referred.subscription_plan, referred.signup_completed, payment.amount
Available actions: credit_reward, send_notification, update_status, trigger_webhook

Return ONLY valid JSON, no explanations."""


class LLMParser:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = None
        self.model = "llama-3.3-70b-versatile"
        
        if GROQ_AVAILABLE and self.api_key:
            self.client = Groq(api_key=self.api_key)
    
    @property
    def is_available(self) -> bool:
        return self.client is not None
    
    def parse(self, natural_language: str) -> dict:
        if self.client:
            return self._parse_with_groq(natural_language)
        return self._parse_locally(natural_language)
    
    def _parse_with_groq(self, text: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=1024
            )
            return self._extract_json(response.choices[0].message.content)
        except Exception as e:
            print(f"Groq error: {e}")
            return self._parse_locally(text)
    
    def _extract_json(self, text: str) -> dict:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}
    
    def _parse_locally(self, text: str) -> dict:
        text_lower = text.lower()
        
        trigger = "referral_signup"
        if "subscri" in text_lower:
            trigger = "subscription_started"
        elif "payment" in text_lower or "pay" in text_lower:
            trigger = "payment_received"
        
        conditions = []
        if "paid user" in text_lower:
            conditions.append({"field": "referrer.is_paid_user", "operator": "equals", "value": True})
        if "premium" in text_lower:
            conditions.append({"field": "referred.subscription_plan", "operator": "equals", "value": "premium"})
        if "vip" in text_lower:
            conditions.append({"field": "referrer.tier", "operator": "equals", "value": "VIP"})
        if not conditions:
            conditions.append({"field": "referred.signup_completed", "operator": "is_true"})
        
        amount = 100
        amount_match = re.search(r'(?:₹|rs\.?|inr|rupees?)\s*(\d+)', text_lower) or \
                       re.search(r'(\d+)\s*(?:₹|rs\.?|inr|rupees?)', text_lower)
        if amount_match:
            amount = int(amount_match.group(1))
        
        reward_type = "cash" if "cash" in text_lower else "voucher"
        
        return {
            "id": f"rule-{hash(text) % 10000:04d}",
            "name": " ".join(text.split()[:5]).title(),
            "description": text,
            "trigger": trigger,
            "conditions": {"operator": "AND", "conditions": conditions} if len(conditions) > 1 else conditions[0],
            "actions": [{"type": "credit_reward", "params": {"amount": amount, "currency": "INR", "reward_type": reward_type}}]
        }


if __name__ == "__main__":
    import sys
    parser = LLMParser(api_key=sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Groq available: {parser.is_available}")
    
    test = "When a paid user refers someone who subscribes to premium, reward 500 rupees"
    print(json.dumps(parser.parse(test), indent=2))
