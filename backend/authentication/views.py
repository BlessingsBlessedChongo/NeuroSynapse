import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import AdminProfile
from authentication.serializers import AdminProfileSerializer, LoginSerializer

logger = logging.getLogger('neurosynapse.authentication')


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class LoginView(APIView):
    """
    POST /api/auth/login/
    Realizes NetworkAdmin.authenticate(password) -> UserSession from the SDS
    class diagram. Issues a DRF auth token used as a bearer token by the
    dashboard frontend for all subsequent requests.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('[AUTH] Failed login attempt from %s', _client_ip(request))
            return Response(
                {'error': 'Invalid credentials.', 'detail': serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)

        profile, _ = AdminProfile.objects.get_or_create(user=user)
        profile.last_login_ip = _client_ip(request)
        profile.save(update_fields=['last_login_ip'])

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        logger.info('[AUTH] User %s logged in from %s', user.username, _client_ip(request))

        return Response({
            'token': token.key,
            'admin': AdminProfileSerializer(profile).data,
        })


class LogoutView(APIView):
    """POST /api/auth/logout/ - invalidates the current session token."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        logger.info('[AUTH] User %s logged out', request.user.username)
        return Response({'status': 'logged out'})


class CurrentAdminView(APIView):
    """GET /api/auth/me/ - returns the authenticated administrator's profile."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = AdminProfile.objects.get_or_create(user=request.user)
        return Response(AdminProfileSerializer(profile).data)
