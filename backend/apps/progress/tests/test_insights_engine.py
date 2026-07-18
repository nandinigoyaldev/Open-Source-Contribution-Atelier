from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from apps.progress.models import ExerciseAttempt, QuizAttempt
from apps.content.models import Lesson, Exercise
from apps.progress.services.insights_engine import InsightsEngine

class InsightsEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="insightuser", password="password", email="insight@test.com")
        self.lesson_python = Lesson.objects.create(
            title="Python Basics",
            slug="python-basics",
            content="Content",
            difficulty="beginner"
        )
        self.lesson_django = Lesson.objects.create(
            title="Django ORM",
            slug="django-orm",
            content="Content",
            difficulty="intermediate"
        )
        self.exercise_python = Exercise.objects.create(
            lesson=self.lesson_python,
            title="Print Hello World",
            prompt="Print hello world",
            expected_command="print('Hello World')",
            points=10
        )
        self.exercise_django = Exercise.objects.create(
            lesson=self.lesson_django,
            title="Filter Query",
            prompt="Filter User",
            expected_command="User.objects.filter()",
            points=20
        )
        
    def test_high_accuracy_insights(self):
        # Create successful attempts
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_python, is_correct=True)
        QuizAttempt.objects.create(user=self.user, question_id="q1", is_correct=True)
        
        insights = InsightsEngine.generate_weekly_insights(self.user)
        self.assertEqual(insights["accuracy_score"], 100)
        self.assertEqual(insights["total_failed_attempts"], 0)
        self.assertIn("exceptional mastery", insights["insight_message"])
        
    def test_struggle_area_detection(self):
        # Create 3 failed attempts for the same lesson to trigger struggle detection
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_python, is_correct=False)
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_python, is_correct=False)
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_python, is_correct=False)
        
        insights = InsightsEngine.generate_weekly_insights(self.user)
        self.assertEqual(insights["accuracy_score"], 0)
        self.assertEqual(insights["total_failed_attempts"], 3)
        self.assertIn("Python Basics", insights["insight_message"])
        self.assertIn("Python Basics", insights["struggle_areas"])
        
    def test_quiz_struggle_detection(self):
        # Create 6 failed quiz attempts
        for i in range(6):
            QuizAttempt.objects.create(user=self.user, question_id=f"q{i}", is_correct=False)
            
        insights = InsightsEngine.generate_weekly_insights(self.user)
        self.assertEqual(insights["accuracy_score"], 0)
        self.assertEqual(insights["total_failed_attempts"], 6)
        self.assertIn("attempting a lot of quizzes", insights["insight_message"])
        
    def test_mixed_accuracy(self):
        # Create 3 correct and 1 failed attempt = 75% accuracy
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_python, is_correct=True)
        ExerciseAttempt.objects.create(user=self.user, exercise=self.exercise_django, is_correct=True)
        QuizAttempt.objects.create(user=self.user, question_id="q1", is_correct=True)
        QuizAttempt.objects.create(user=self.user, question_id="q2", is_correct=False)
        
        insights = InsightsEngine.generate_weekly_insights(self.user)
        self.assertEqual(insights["accuracy_score"], 75)
        self.assertIn("solid steady learning path", insights["insight_message"])
