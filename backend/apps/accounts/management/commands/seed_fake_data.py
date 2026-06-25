import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker

from apps.accounts.models import UserProfile
from apps.content.models import Exercise, Lesson
from apps.progress.models import ExerciseAttempt, HelpRequest, LessonProgress

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds the database with realistic fake user data, progress, and issues for load testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=1000,
            help="Number of fake users to generate",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete existing fake data before seeding",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        clean = options["clean"]
        fake = Faker()

        if clean:
            self.stdout.write("Cleaning up existing fake data...")
            users_to_delete = User.objects.filter(username__startswith="fake_")
            count, _ = users_to_delete.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {count} fake users and their related data.")
            )

        self.stdout.write(f"Generating {num_users} fake users...")

        users_to_create = []
        for _ in range(num_users):
            username = f"fake_{fake.user_name()}_{fake.random_int(min=1000, max=99999)}"
            email = fake.email()
            first_name = fake.first_name()
            last_name = fake.last_name()
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
            )
            # Cannot use set_password with bulk_create, so we will not set usable passwords
            # to keep bulk_create fast. Load testing mostly doesn't require login, or 
            # we can hash one password and assign it to all.
            users_to_create.append(user)

        # Bulk create users
        created_users = User.objects.bulk_create(users_to_create)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {len(created_users)} users.")
        )

        # Re-fetch users to get IDs for related objects
        # Note: bulk_create doesn't always set PKs (depending on DB). Fetching again is safe.
        fake_users = list(
            User.objects.filter(username__startswith="fake_").order_by("-id")[:num_users]
        )

        # Create user profiles because bulk_create bypasses the post_save signal
        profiles_to_create = [UserProfile(user=u) for u in fake_users]
        UserProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS("Ensured user profiles exist."))

        # Generate progress records
        lessons = list(Lesson.objects.all())
        exercises = list(Exercise.objects.all())

        lesson_progress_to_create = []
        exercise_attempts_to_create = []
        help_requests_to_create = []

        if not lessons:
            self.stdout.write(
                self.style.WARNING("No lessons found. Skipping progress generation.")
            )
        else:
            self.stdout.write("Generating lesson progress and exercise attempts...")
            for user in fake_users:
                # User completes 1 to N lessons
                num_lessons_to_complete = random.randint(0, min(10, len(lessons)))
                completed_lessons = random.sample(lessons, k=num_lessons_to_complete)
                for lesson in completed_lessons:
                    lesson_progress_to_create.append(
                        LessonProgress(
                            user=user,
                            lesson=lesson,
                            completed=random.choice([True, False]),
                            score=random.randint(0, 100),
                            attempt_count=random.randint(1, 5),
                        )
                    )

                # User attempts 1 to N exercises
                if exercises:
                    num_ex_to_attempt = random.randint(0, min(10, len(exercises)))
                    attempted_exercises = random.sample(exercises, k=num_ex_to_attempt)
                    for ex in attempted_exercises:
                        is_correct = random.choice([True, False])
                        cmd = (
                            ex.expected_command
                            if is_correct
                            else fake.sentence(nb_words=4)
                        )
                        exercise_attempts_to_create.append(
                            ExerciseAttempt(
                                user=user,
                                exercise=ex,
                                submitted_command=cmd[:255],
                                is_correct=is_correct,
                            )
                        )

                # User makes 0 to 3 help requests
                for _ in range(random.randint(0, 3)):
                    help_requests_to_create.append(
                        HelpRequest(
                            user=user,
                            lesson=random.choice(lessons),
                            message=fake.paragraph(),
                            status=random.choice(
                                [HelpRequest.Status.OPEN, HelpRequest.Status.RESOLVED]
                            ),
                        )
                    )

        if lesson_progress_to_create:
            LessonProgress.objects.bulk_create(lesson_progress_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {len(lesson_progress_to_create)} lesson progress records."
                )
            )

        if exercise_attempts_to_create:
            ExerciseAttempt.objects.bulk_create(exercise_attempts_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {len(exercise_attempts_to_create)} exercise attempts."
                )
            )

        if help_requests_to_create:
            HelpRequest.objects.bulk_create(help_requests_to_create)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {len(help_requests_to_create)} help requests (issues)."
                )
            )

        self.stdout.write(self.style.SUCCESS("Database seeding completed!"))
