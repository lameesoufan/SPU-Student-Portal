from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import User
from .throttles import LoginRateThrottle


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role']                 = user.role
        token['username']             = user.username
        token['must_change_password'] = user.must_change_password
        token['must_change_username'] = user.must_change_username
        token['department']           = user.department
        return token

    def validate(self, attrs):
        username = attrs.get('username', '').strip()
        password = attrs.get('password', '').strip()

        authenticated_user = authenticate(username=username, password=password)
        if authenticated_user and authenticated_user.is_superuser and authenticated_user.role != 'dean':
            authenticated_user.role = 'dean'
            authenticated_user.save(update_fields=['role'])

        # Proceed with standard JWT validation (checks password etc.)
        return super().validate(attrs)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']


class ImportExcelSerializer(serializers.Serializer):
    file = serializers.FileField()
    role = serializers.ChoiceField(choices=[('student', 'Student'), ('doctor', 'Doctor')])