from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from authentication.models import AdminProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_admin_profile(sender, instance, created, **kwargs):
    """
    Ensures every Django User has a corresponding AdminProfile.
    Superusers created via 'createsuperuser' automatically receive the
    SUPER_ADMIN role so the system is usable immediately after setup.
    """
    if not created:
        return

    role = AdminProfile.ROLE_SUPER_ADMIN if instance.is_superuser else AdminProfile.ROLE_ADMIN
    AdminProfile.objects.get_or_create(user=instance, defaults={'role': role})
