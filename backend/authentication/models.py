from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    """
    Extends Django's built-in User model to realize the 'NetworkAdmin' class
    from the System Design Specification (Figure 4.4 Class Diagram).

    The SDS defines NetworkAdmin with:
      +String adminID
      +String role
      +authenticate(password: String): UserSession
      +manualACK(actionId: int): boolean
      +viewXAI(incidentId: String): JSON

    `authenticate` is realized via the /api/auth/login/ endpoint (token
    issuance). `manualACK` is realized via the incident approve/reject
    endpoints in the dashboard app. `viewXAI` is realized via the XAI
    explanation endpoints in the dashboard app.
    """

    ROLE_SUPER_ADMIN = 'SUPER_ADMIN'
    ROLE_ADMIN = 'ADMIN'
    ROLE_VIEWER = 'VIEWER'

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, 'Super Administrator'),
        (ROLE_ADMIN, 'Network Administrator'),
        (ROLE_VIEWER, 'Read-Only Viewer'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Network Administrator Profile'
        verbose_name_plural = 'Network Administrator Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def admin_id(self):
        """Maps to the SDS 'adminID' attribute."""
        return str(self.user.id)

    def can_approve_actions(self):
        """Only ADMIN and SUPER_ADMIN roles may approve/reject/rollback."""
        return self.role in (self.ROLE_SUPER_ADMIN, self.ROLE_ADMIN)

    def can_configure_policies(self):
        """Only SUPER_ADMIN may edit healing policy thresholds."""
        return self.role == self.ROLE_SUPER_ADMIN
