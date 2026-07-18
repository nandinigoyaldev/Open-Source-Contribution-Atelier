"""
Management command to check lock status.
"""

from django.core.management.base import BaseCommand
from apps.core.locks import TaskLockManager


class Command(BaseCommand):
    help = "Check and manage distributed locks"

    def add_arguments(self, parser):
        parser.add_argument(
            '--release',
            type=str,
            help='Force release a specific lock'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all active locks'
        )

    def handle(self, *args, **options):
        if options.get('release'):
            lock_key = options['release']
            self.stdout.write(f"Releasing lock: {lock_key}")
            if TaskLockManager.force_release(lock_key):
                self.stdout.write(f"✅ Lock {lock_key} released")
            else:
                self.stdout.write(f"❌ Failed to release lock {lock_key}")
            return

        if options.get('all'):
            locks = TaskLockManager.get_all_locks()
            if locks:
                self.stdout.write(f"Active locks ({len(locks)}):")
                for lock in locks:
                    info = TaskLockManager.get_lock_info(lock)
                    if info:
                        self.stdout.write(f"  - {lock} (TTL: {info['ttl']}s)")
            else:
                self.stdout.write("No active locks")
            return

        self.stdout.write("Lock Status:")
        self.stdout.write("  Use --all to list all locks")
        self.stdout.write("  Use --release <key> to force release a lock")