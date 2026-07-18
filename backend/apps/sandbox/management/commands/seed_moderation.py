import uuid
from django.core.management.base import BaseCommand
from apps.sandbox.models import ModerationScenario, DialogueNode, DialogueChoice


class Command(BaseCommand):
    help = "Seeds initial Moderation scenarios."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Moderation Scenarios...")

        # Scenario 1: A user is very angry about a breaking change
        scenario1, created = ModerationScenario.objects.get_or_create(
            title="Angry User on Breaking Change",
            defaults={
                "description": "A user is furiously complaining about a breaking change in a minor release and demanding an immediate fix, using passive-aggressive language.",
                "initial_tension": 70,
            },
        )

        if not created:
            self.stdout.write("Scenario 1 already exists, skipping...")
        else:
            # Nodes
            start_node = DialogueNode.objects.create(
                scenario=scenario1,
                node_id="start",
                text="User: This project is a complete joke! You broke my production app with your stupid minor release! Fix it NOW or I'm moving to another library. This is totally unacceptable!",
            )

            aggro_reply = DialogueNode.objects.create(
                scenario=scenario1,
                node_id="aggro_reply",
                text="User: Wow, so you're just going to insult me? Forget this, you clearly don't care about your users. I'm reporting this repo.",
                is_endpoint=True,
                is_successful=False,
            )

            empathic_reply = DialogueNode.objects.create(
                scenario=scenario1,
                node_id="empathic_reply",
                text="User: Okay... sorry for yelling. I'm just stressed because it took down our servers. We will pin the version for now. Could you please update the changelog to note the breaking change?",
            )

            end_success = DialogueNode.objects.create(
                scenario=scenario1,
                node_id="end_success",
                text="User: Thanks, I appreciate you understanding. I'll read the docs more carefully next time.",
                is_endpoint=True,
                is_successful=True,
            )

            # Choices from start
            DialogueChoice.objects.create(
                from_node=start_node,
                to_node_id="aggro_reply",
                text="[Aggressive] Tell them to calm down and stop being entitled. Open source is free.",
                tension_delta=30,
            )
            DialogueChoice.objects.create(
                from_node=start_node,
                to_node_id="empathic_reply",
                text="[Empathetic & Firm] I understand the frustration of a broken build, but please keep the conversation respectful per our CoC. The change was documented, but we can clarify it.",
                tension_delta=-30,
            )

            # Choices from empathic_reply
            DialogueChoice.objects.create(
                from_node=empathic_reply,
                to_node_id="end_success",
                text="[Helpful] I've just updated the changelog. Thanks for pointing out the confusion. Let me know if pinning the version works for you.",
                tension_delta=-20,
            )
            DialogueChoice.objects.create(
                from_node=empathic_reply,
                to_node_id="aggro_reply",
                text="[Dismissive] Yeah well you should have read the docs before upgrading blindly.",
                tension_delta=50,
            )

            self.stdout.write(
                self.style.SUCCESS("Successfully seeded Moderation Scenarios.")
            )
