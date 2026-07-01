import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from .models import Lesson, Module, Quiz, Question, LessonProgress, User

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user_{n}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True


class ModuleFactory(DjangoModelFactory):
    """Factory for creating content modules"""
    class Meta:
        model = Module

    title = factory.Sequence(lambda n: f"Module {n}")
    description = factory.Faker('paragraph')
    slug = factory.Sequence(lambda n: f"module-{n}")
    order = factory.Sequence(lambda n: n)
    is_published = True


class LessonFactory(DjangoModelFactory):
    """Factory for creating lessons"""
    class Meta:
        model = Lesson

    title = factory.Sequence(lambda n: f"Lesson {n}")
    slug = factory.Sequence(lambda n: f"lesson-{n}")
    content = factory.Faker('paragraph', nb_sentences=10)
    description = factory.Faker('sentence')
    module = factory.SubFactory(ModuleFactory)
    order = factory.Sequence(lambda n: n)
    learning_objectives = factory.Faker('paragraph')
    tips = factory.Faker('sentence')
    prerequisites = factory.Faker('sentence')
    is_published = True


class QuizFactory(DjangoModelFactory):
    """Factory for creating quizzes"""
    class Meta:
        model = Quiz

    title = factory.Sequence(lambda n: f"Quiz {n}")
    description = factory.Faker('sentence')
    lesson = factory.SubFactory(LessonFactory)
    passing_score = 70
    is_published = True


class QuestionFactory(DjangoModelFactory):
    """Factory for creating quiz questions"""
    class Meta:
        model = Question

    text = factory.Faker('sentence')
    quiz = factory.SubFactory(QuizFactory)
    correct_answer = factory.Faker('word')
    points = 10
    order = factory.Sequence(lambda n: n)


class LessonProgressFactory(DjangoModelFactory):
    """Factory for tracking lesson progress"""
    class Meta:
        model = LessonProgress

    user = factory.SubFactory(UserFactory)
    lesson = factory.SubFactory(LessonFactory)
    completed = factory.Faker('boolean')
    score = factory.Faker('random_int', min=0, max=100)


class ModuleProgressFactory(DjangoModelFactory):
    """Factory for tracking module progress"""
    class Meta:
        model = ModuleProgress

    user = factory.SubFactory(UserFactory)
    module = factory.SubFactory(ModuleFactory)
    completed = factory.Faker('boolean')
    progress_percentage = factory.Faker('random_int', min=0, max=100)


# ====== Helper Factories with Related Data ======

class ModuleWithLessonsFactory(ModuleFactory):
    """Creates a module with 5 lessons"""
    
    @factory.post_generation
    def create_lessons(self, create, extracted, **kwargs):
        if not create:
            return
        LessonFactory.create_batch(5, module=self)


class LessonWithQuizFactory(LessonFactory):
    """Creates a lesson with a quiz"""
    
    @factory.post_generation
    def create_quiz(self, create, extracted, **kwargs):
        if not create:
            return
        quiz = QuizFactory(lesson=self)
        QuestionFactory.create_batch(5, quiz=quiz)


class CompleteModuleFactory(ModuleFactory):
    """Creates a complete module with lessons and quizzes"""
    
    @factory.post_generation
    def create_content(self, create, extracted, **kwargs):
        if not create:
            return
        for i in range(3):
            lesson = LessonFactory(module=self, order=i+1)
            quiz = QuizFactory(lesson=lesson)
            QuestionFactory.create_batch(3, quiz=quiz)


class QuizWithQuestionsFactory(QuizFactory):
    """Creates a quiz with 5 questions"""
    
    @factory.post_generation
    def create_questions(self, create, extracted, **kwargs):
        if not create:
            return
        QuestionFactory.create_batch(5, quiz=self)