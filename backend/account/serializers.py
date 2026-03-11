from rest_framework import serializers

from .models import User, UserPreferences


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
            "username",
        )


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ("kanban_column_order", "updated_at")
        read_only_fields = ("updated_at",)
