from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "username", "role", "is_staff", "is_blocked")
    list_filter = ("is_staff", "is_blocked", "role")
    search_fields = ("email", "username")
    ordering = ("email",)
