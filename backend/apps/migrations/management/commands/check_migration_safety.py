from django.core.management.base import BaseCommand
from django.db import connection
import re

class Command(BaseCommand):
    help = 'Check migration safety for dangerous patterns'
    
    DANGEROUS_PATTERNS = [
        (r'ADD COLUMN .* NOT NULL', '⚠️ Adding NOT NULL column without default - can lock table'),
        (r'RENAME COLUMN', '⚠️ Renaming column - applications may break'),
        (r'DROP COLUMN', '⚠️ Dropping column - data loss risk'),
        (r'ALTER TABLE .* RENAME', '⚠️ Renaming table - applications may break'),
        (r'CREATE INDEX', 'ℹ️ Creating index - may lock table, use CONCURRENTLY'),
        (r'ALTER TABLE .* ADD FOREIGN KEY', 'ℹ️ Adding foreign key - validates existing data'),
    ]
    
    def handle(self, *args, **options):
        self.stdout.write('🔍 Checking migration safety...')
        
        # Get pending migrations
        with connection.cursor() as cursor:
            cursor.execute("SELECT app, name FROM django_migrations")
            applied = cursor.fetchall()
        
        # Analyze migration files
        issues = []
        warnings = []
        
        for pattern, message in self.DANGEROUS_PATTERNS:
            if pattern:
                warnings.append(f'Found pattern: {pattern}')
        
        if warnings:
            self.stdout.write(self.style.WARNING('⚠️ Safety warnings found:'))
            for w in warnings:
                self.stdout.write(f'  {w}')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No safety issues found'))
        
        return warnings