"""
Role-Based Access Control (RBAC) permission classes.
Satisfies the SDS Security Requirement:
'Role-Based Access Control shall be enforced for all dashboard functions.'
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from authentication.models import AdminProfile


def _get_profile(request):
    if not request.user or not request.user.is_authenticated:
        return None
    profile, _ = AdminProfile.objects.get_or_create(user=request.user)
    return profile


class IsNetworkAdministrator(BasePermission):
    """
    Allows read access (GET/HEAD/OPTIONS) to any authenticated user.
    Allows write access only to ADMIN or SUPER_ADMIN roles.
    Used for actions such as approving healing decisions, triggering
    rollbacks, and managing devices.
    """

    message = 'This action requires Network Administrator privileges.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = _get_profile(request)
        return bool(profile and profile.can_approve_actions())


class IsSuperAdministrator(BasePermission):
    """
    Allows read access to any authenticated user.
    Allows write access only to SUPER_ADMIN (used for policy/threshold
    configuration, since misconfigured thresholds affect all devices).
    """

    message = 'This action requires Super Administrator privileges.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = _get_profile(request)
        return bool(profile and profile.can_configure_policies())
