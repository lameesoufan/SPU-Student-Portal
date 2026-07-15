"""
Management command to cleanup expired OTP codes.
Run this periodically (e.g., daily via cron or celery beat).
"""
from django.core.management.base import BaseCommand
from accounts.services import cleanup_expired_otps


class Command(BaseCommand):
    help = 'Delete expired OTP codes older than 24 hours'

    def handle(self, *args, **options):
        self.stdout.write('Cleaning up expired OTP codes...')
        
        deleted_count = cleanup_expired_otps()
        
        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {deleted_count} expired OTP record(s)')
            )
        else:
            self.stdout.write('No expired OTP records to delete')
