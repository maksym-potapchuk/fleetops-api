from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "role",
            "is_email_verified",
            "is_blocked",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id", 
            "created_at", 
            "updated_at", 
            "is_blocked", 
            "is_email_verified", 
            "role", 
            "email", 
            "username"
        )