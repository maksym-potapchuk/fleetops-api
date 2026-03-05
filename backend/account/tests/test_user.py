"""
User Tests
==========
Covers: UserMeAPIView, User model.

Focus areas:
- Read-only field protection (role, email, username, is_blocked, is_email_verified)
- Security: users cannot self-elevate permissions
"""

import uuid

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User

from .helpers import authenticate, make_user


class UserMeAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user(
            email="me@example.com",
            password="pass123!",
            username="meuser",
            first_name="Jan",
            last_name="Kowalski",
        )
        authenticate(self.client, self.user)

    def test_get_profile_returns_200(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)

    def test_get_profile_returns_correct_fields(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["username"], "meuser")
        self.assertEqual(response.data["first_name"], "Jan")

    def test_get_profile_does_not_expose_password(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertNotIn("password", response.data)

    def test_unauthenticated_get_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    # --- PATCH — allowed fields ---

    def test_patch_first_name_succeeds(self):
        response = self.client.patch(
            "/api/v1/auth/me/", {"first_name": "Updated"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_patch_last_name_succeeds(self):
        response = self.client.patch(
            "/api/v1/auth/me/", {"last_name": "Nowak"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Nowak")

    def test_patch_phone_succeeds(self):
        response = self.client.patch(
            "/api/v1/auth/me/", {"phone": "+48123456789"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+48123456789")

    # --- PATCH — read-only fields (security tests) ---

    def test_patch_email_is_silently_ignored(self):
        """
        SECURITY: email is read_only in UserSerializer.
        A PATCH must not change the stored email.
        """
        response = self.client.patch(
            "/api/v1/auth/me/", {"email": "hacked@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.email,
            "me@example.com",
            "SECURITY: email must not be changeable via /me/ PATCH",
        )

    def test_patch_role_is_silently_ignored(self):
        """SECURITY: users must not be able to assign themselves a role."""
        response = self.client.patch(
            "/api/v1/auth/me/", {"role": "admin"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertNotEqual(
            self.user.role,
            "admin",
            "SECURITY: role must not be settable via /me/ PATCH",
        )

    def test_patch_username_is_silently_ignored(self):
        """SECURITY: users must not be able to change their own username."""
        response = self.client.patch(
            "/api/v1/auth/me/", {"username": "hackername"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.username,
            "meuser",
            "SECURITY: username must not be changeable via /me/ PATCH",
        )

    def test_patch_is_blocked_is_silently_ignored(self):
        """SECURITY: a blocked user must not be able to unblock themselves."""
        self.user.is_blocked = True
        self.user.save()
        response = self.client.patch(
            "/api/v1/auth/me/", {"is_blocked": False}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.is_blocked,
            "SECURITY: users must not be able to unblock themselves via /me/",
        )

    def test_patch_is_email_verified_is_silently_ignored(self):
        """SECURITY: users must not be able to self-verify their email."""
        response = self.client.patch(
            "/api/v1/auth/me/", {"is_email_verified": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(
            self.user.is_email_verified,
            "SECURITY: is_email_verified must not be settable via /me/ PATCH",
        )

    def test_unauthenticated_patch_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.patch(
            "/api/v1/auth/me/", {"first_name": "Hacker"}, format="json"
        )
        self.assertEqual(response.status_code, 401)


# ===========================================================================
# User Model Tests
# ===========================================================================


class UserModelTest(TestCase):
    def test_create_user_stores_email_correctly(self):
        user = make_user()
        self.assertEqual(user.email, "test@example.com")

    def test_password_is_hashed(self):
        user = make_user()
        self.assertNotEqual(user.password, "pass123!")
        self.assertTrue(user.check_password("pass123!"))

    def test_user_id_is_uuid(self):
        user = make_user()
        self.assertIsInstance(user.id, uuid.UUID)

    def test_email_must_be_unique(self):
        make_user()
        with self.assertRaises(IntegrityError):
            make_user(username="other")  # same email, different username

    def test_username_must_be_unique(self):
        make_user()
        with self.assertRaises(IntegrityError):
            make_user(email="other@example.com")  # different email, same username

    def test_create_user_without_email_raises_value_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass", username="u")

    def test_is_email_verified_defaults_to_false(self):
        user = make_user()
        self.assertFalse(user.is_email_verified)

    def test_is_blocked_defaults_to_false(self):
        user = make_user()
        self.assertFalse(user.is_blocked)

    def test_is_active_defaults_to_true(self):
        user = make_user()
        self.assertTrue(user.is_active)

    def test_str_representation_is_email(self):
        user = make_user()
        self.assertEqual(str(user), "test@example.com")

    def test_create_superuser_sets_is_staff_and_is_superuser(self):
        superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass",
            username="admin",
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_without_is_staff_raises_value_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="fail@example.com",
                password="pass",
                username="fail",
                is_staff=False,
            )

    def test_create_superuser_without_is_superuser_raises_value_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="fail2@example.com",
                password="pass",
                username="fail2",
                is_superuser=False,
            )
