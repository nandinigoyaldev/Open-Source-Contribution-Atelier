"""
Management command to initialize event system.
"""

from django.core.management.base import BaseCommand
from apps.events.registry import init_event_handlers
from apps.events.models import EventSubscription


class Command(BaseCommand):
    """
    Initialize the event system.
    """
    
    help = 'Initialize event system with default subscriptions'
    
    def handle(self, *args, **options):
        self.stdout.write('Initializing event system...')
        
        # Initialize handlers
        init_event_handlers()
        self.stdout.write('✓ Event handlers initialized')
        
        # Create default subscriptions
        default_subscriptions = [
            ('apps.events.handlers.handle_lesson_completed', ['LessonCompleted']),
            ('apps.events.handlers.handle_quiz_completed', ['QuizCompleted']),
            ('apps.events.handlers.handle_badge_unlocked', ['BadgeUnlocked']),
            ('apps.events.handlers.handle_certificate_generated', ['CertificateGenerated']),
            ('apps.events.handlers.handle_streak_updated', ['StreakUpdated']),
            ('apps.events.handlers.handle_module_completed', ['ModuleCompleted']),
            ('apps.events.handlers.handle_event_for_analytics', ['LessonCompleted', 'QuizCompleted', 'BadgeUnlocked']),
            ('apps.events.handlers.handle_event_for_notifications', ['LessonCompleted', 'BadgeUnlocked', 'CertificateGenerated']),
        ]
        
        created_count = 0
        for subscriber, event_types in default_subscriptions:
            subscription, created = EventSubscription.objects.get_or_create(
                subscriber=subscriber,
                defaults={
                    'event_types': event_types,
                    'is_active': True,
                    'priority': 0
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(f'✓ Created {created_count} event subscriptions')
        self.stdout.write('✅ Event system initialized successfully!')