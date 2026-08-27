"""
Create a NeuroSynapse dashboard administrator account.

Usage:
    python manage.py create_admin --username admin --password secret --role SUPER_ADMIN
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from authentication.models import AdminProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or update a NeuroSynapse administrator account.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--email', default='')
        parser.add_argument(
            '--role',
            default=AdminProfile.ROLE_ADMIN,
            choices=[choice[0] for choice in AdminProfile.ROLE_CHOICES],
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        role = options['role']

        if len(password) < 8:
            raise CommandError('[ERROR] Password must be at least 8 characters.')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        user.set_password(password)
        user.email = email or user.email
        user.is_staff = True
        if role == AdminProfile.ROLE_SUPER_ADMIN:
            user.is_superuser = True
        user.save()

        profile, _ = AdminProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.save(update_fields=['role'])

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f"[OK] {action} administrator '{username}' with role {role}"
        ))
