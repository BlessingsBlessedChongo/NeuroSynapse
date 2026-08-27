from django.contrib.auth import authenticate
from rest_framework import serializers

from authentication.models import AdminProfile


class LoginSerializer(serializers.Serializer):
    """Validates login credentials (Secure Authentication user requirement)."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get('username'),
            password=attrs.get('password'),
        )
        if user is None:
            raise serializers.ValidationError('Invalid username or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account has been disabled.')
        attrs['user'] = user
        return attrs


class AdminProfileSerializer(serializers.ModelSerializer):
    admin_id = serializers.CharField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = AdminProfile
        fields = ['admin_id', 'username', 'email', 'role', 'created_at']
        read_only_fields = fields
