from apps.content.models import Lesson
from apps.progress.models import Certificate, LessonProgress
from django.contrib.auth.models import User

# Create user
user, created = User.objects.get_or_create(
    username="teststudent", defaults={"first_name": "Test", "last_name": "Student"}
)
user.set_password("password123")
user.save()

# Ensure we have at least one lesson so they can be "100%" complete
if not Lesson.objects.exists():
    Lesson.objects.create(
        slug="test-lesson", title="Introduction to Open Source", difficulty="beginner"
    )

# Mark all lessons complete for this user
for lesson in Lesson.objects.all():
    progress, _ = LessonProgress.objects.get_or_create(user=user, lesson=lesson)
    progress.completed = True
    progress.save()

# Auto-generate the certificate explicitly so we can print the hash for them
cert, _ = Certificate.objects.get_or_create(
    user=user, defaults={"course_name": "Open Source Contribution Course"}
)

print("=========================================")
print("✅ TEST ACCOUNT CREATED SUCCESSFULLY ✅")
print("=========================================")
print("Login URL: http://localhost:5174/login (or 5173 depending on your terminal)")
print("Username: teststudent")
print("Password: password123")
print(f"Certificate Hash generated: {cert.verification_hash}")
print("=========================================")
