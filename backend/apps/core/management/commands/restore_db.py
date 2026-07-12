import os
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'Restore the PostgreSQL database from a pg_dump file'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to the backup file to restore')

    def handle(self, *args, **options):
        backup_file = options['file']
        
        if not os.path.exists(backup_file):
            raise CommandError(f'Backup file not found: {backup_file}')

        db_settings = settings.DATABASES['default']
        engine = db_settings.get('ENGINE', '')
        
        if 'postgresql' not in engine:
            raise CommandError('This command only supports PostgreSQL databases.')
            
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings.get('PASSWORD', '')
        db_host = db_settings.get('HOST', 'localhost')
        db_port = db_settings.get('PORT', '5432')
        
        env = os.environ.copy()
        if db_password:
            env['PGPASSWORD'] = str(db_password)
            
        command = [
            'pg_restore',
            '-h', str(db_host),
            '-p', str(db_port),
            '-U', str(db_user),
            '-d', str(db_name),
            '--clean',  # Drop objects before creating
            '--if-exists',
            '-1', # Single transaction
            str(backup_file)
        ]
        
        self.stdout.write(self.style.NOTICE(f'Starting restore of database {db_name} from {backup_file}...'))
        try:
            subprocess.run(command, env=env, check=True)
            self.stdout.write(self.style.SUCCESS(f'Successfully restored database from {backup_file}'))
        except subprocess.CalledProcessError as e:
            raise CommandError(f'Restore failed: {e}')
