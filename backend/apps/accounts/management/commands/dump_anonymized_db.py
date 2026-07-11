import hashlib

from django.core.management.commands.dumpdata import Command as DumpDataCommand
from django.core.serializers.json import Serializer as BaseJSONSerializer
from faker import Faker

# Declarative PII rules mapping `app_label.model_name` -> `field_name` -> `strategy`
# Extensible without modifying the command logic.
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
    "content.lessonthread": {
        "title": "sentence",
        "content": "paragraph",
    },
    "content.lessoncomment": {
        "content": "paragraph",
    },
    "content.comment": {
        "content": "paragraph",
    },
    "content.lessonfeedback": {
        "comment": "paragraph",
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
            # Seed faker with a deterministic hash of the model and PK for reproducible tests
            seed_val = int(
                hashlib.md5(f"{model_label}_{pk}".encode()).hexdigest()[:8], 16
            )
            self.faker.seed_instance(seed_val)

        for field_name, strategy in rules.items():
            if field_name not in fields_dict:
                continue

            # Original value is sometimes useful for conditions (e.g., preserving nulls)
            original_value = fields_dict[field_name]
            if original_value is None:
                continue  # Preserve nulls rather than injecting fake data

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


# Global engine instance for the serializer to access
engine = AnonymizationEngine()


class Serializer(BaseJSONSerializer):
    """
    Custom JSON Serializer that intercepts `get_dump_object` to anonymize
    the dictionary payload before Django's base JSON serializer stringifies it.
    """

    def get_dump_object(self, obj):
        data = super().get_dump_object(obj)
        model_label = obj._meta.label_lower
        data["fields"] = engine.anonymize(model_label, data["fields"], obj.pk)
        return data


class Command(DumpDataCommand):
    help = "Dumps an anonymized JSON fixture of the database, masking PII using Faker."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--deterministic",
            action="store_true",
            help="Generate consistent fake data across runs based on row PKs (for reproducible testing)",
        )

    def handle(self, *app_labels, **options):
        # Configure the engine based on command options
        engine.setup(deterministic=options.get("deterministic"))

        from django.core import serializers

        # Register this very module as a serializer named 'anon-json'
        # Django will look for the `Serializer` class defined above.
        serializers.register_serializer(
            "anon-json", "apps.accounts.management.commands.dump_anonymized_db"
        )

        # Force format to use our custom serializer
        options["format"] = "anon-json"

        # Delegate everything else (exclude, natural keys, file output, batching) to the base dumpdata
        return super().handle(*app_labels, **options)
