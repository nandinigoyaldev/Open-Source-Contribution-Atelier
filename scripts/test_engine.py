import json
import sys
import os

# Add the backend dir to sys.path so we can import the command
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# We don't have django initialized, so we will extract the AnonymizationEngine class directly 
# to show how it processes data dictionaries.

from faker import Faker
import hashlib

PII_RULES = {
    "auth.user": {
        "username": "user_name",
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "password": "fixed:pbkdf2_sha256$600000$dummy$dummy",
    },
    "accounts.userprofile": {
        "twitter_url": "clear",
        "linkedin_url": "clear",
        "github_url": "clear",
    },
    "progress.helprequest": {
        "message": "paragraph",
    },
}

class AnonymizationEngine:
    def __init__(self):
        self.faker = Faker()
        self.deterministic = False

    def setup(self, deterministic=False):
        self.deterministic = deterministic

    def anonymize(self, model_label, fields_dict, pk):
        rules = PII_RULES.get(model_label)
        if not rules:
            return fields_dict

        if self.deterministic:
            seed_val = int(
                hashlib.md5(f"{model_label}_{pk}".encode()).hexdigest()[:8], 16
            )
            self.faker.seed_instance(seed_val)

        for field_name, strategy in rules.items():
            if field_name not in fields_dict:
                continue

            original_value = fields_dict[field_name]
            if original_value is None:
                continue

            if strategy == "clear":
                fields_dict[field_name] = ""
            elif strategy.startswith("fixed:"):
                fields_dict[field_name] = strategy.split("fixed:", 1)[1]
            elif hasattr(self.faker, strategy):
                provider = getattr(self.faker, strategy)
                if strategy == "user_name":
                    fields_dict[field_name] = f"anon_{provider()}_{pk}"
                else:
                    fields_dict[field_name] = provider()
            else:
                fields_dict[field_name] = "[ANONYMIZED]"

        return fields_dict

def run_tests():
    engine = AnonymizationEngine()
    engine.setup(deterministic=True)
    
    print("=== Testing auth.user ===")
    user_data = {
        "username": "real_suhas",
        "email": "suhas.real@example.com",
        "first_name": "Suhas",
        "last_name": "Kumar",
        "password": "pbkdf2_sha256$600000$myrealpassword$hash",
        "is_active": True,
        "date_joined": "2026-07-09T10:00:00Z"
    }
    
    print("Original User:", json.dumps(user_data, indent=2))
    anon_user = engine.anonymize("auth.user", user_data.copy(), pk=42)
    print("\nAnonymized User:", json.dumps(anon_user, indent=2))
    
    print("\n=== Testing accounts.userprofile ===")
    profile_data = {
        "user": 42,
        "timezone": "UTC",
        "twitter_url": "https://twitter.com/realsuhas",
        "github_url": "https://github.com/realsuhas",
    }
    
    print("Original Profile:", json.dumps(profile_data, indent=2))
    anon_profile = engine.anonymize("accounts.userprofile", profile_data.copy(), pk=10)
    print("\nAnonymized Profile:", json.dumps(anon_profile, indent=2))
    
    print("\n=== Testing unconfigured model (content.lesson) ===")
    lesson_data = {
        "title": "React Basics",
        "content": "Learn React from scratch."
    }
    print("Original Lesson:", json.dumps(lesson_data, indent=2))
    anon_lesson = engine.anonymize("content.lesson", lesson_data.copy(), pk=5)
    print("\nAnonymized Lesson:", json.dumps(anon_lesson, indent=2))

if __name__ == "__main__":
    run_tests()
