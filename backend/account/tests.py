"""
Account / Auth Test Suite
=========================
Covers: LoginView, RefreshView, LogoutView, UserMeAPIView, User model.

Focus areas:
- Cookie-based JWT authentication
- Tokens must NOT be exposed in response body
- Read-only field protection (role, email, username, is_blocked, is_email_verified)
- Proper 401 for unauthenticated requests
- Security: users cannot self-elevate permissions
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_user(
    email="test@example.com",
    password="pass123!",
    username="testuser",
    **extra,
):
    return User.objects.create_user(
        email=email, password=password, username=username, **extra
    )


def authenticate(client: APIClient, user: User) -> None:
    """Injects a valid cookie-based JWT into an APIClient."""
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)


# ===========================================================================
# 1. LoginView Tests
# ===========================================================================


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_valid_credentials_return_200(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertEqual(response.status_code, 200)

    def test_response_body_contains_only_detail_ok(self):
        """Tokens must NOT appear in the response body — only in httponly cookies."""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertEqual(response.data, {"detail": "ok"})
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_access_token_cookie_is_set(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertIn("access_token", response.cookies)

    def test_refresh_token_cookie_is_set(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertIn("refresh_token", response.cookies)

    def test_access_token_cookie_is_httponly(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertTrue(response.cookies["access_token"]["httponly"])

    def test_refresh_token_cookie_is_httponly(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, 401)

    def test_nonexistent_email_returns_401(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nobody@example.com", "password": "pass123!"},
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_password_returns_400(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com"}
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_email_returns_400(self):
        response = self.client.post("/api/v1/auth/login/", {"password": "pass123!"})
        self.assertEqual(response.status_code, 400)

    def test_empty_body_returns_400(self):
        response = self.client.post("/api/v1/auth/login/", {})
        self.assertEqual(response.status_code, 400)

    def test_inactive_user_cannot_login(self):
        """
        Django's authenticate() rejects is_active=False users by default.
        Inactive (blocked) accounts must not receive tokens.
        """
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertIn(response.status_code, [400, 401])

    def test_sql_injection_in_email_field_does_not_cause_500(self):
        """Malformed email input must not cause a 500 error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "' OR '1'='1", "password": "anything"},
        )
        self.assertNotEqual(response.status_code, 500)


# ===========================================================================
# 2. RefreshView Tests
# ===========================================================================


class RefreshViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def _login(self):
        return self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )

    def test_refresh_with_valid_token_returns_200(self):
        self._login()
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, 200)

    def test_refresh_response_body_is_detail_refreshed(self):
        """New access token must be in the cookie, not in the response body."""
        self._login()
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.data, {"detail": "refreshed"})
        self.assertNotIn("access", response.data)

    def test_refresh_sets_new_access_token_cookie(self):
        self._login()
        response = self.client.post("/api/v1/auth/refresh/")
        self.assertIn("access_token", response.cookies)

    def test_refresh_without_cookie_returns_error(self):
        """Attempting to refresh without a cookie must fail."""
        fresh_client = APIClient()
        response = fresh_client.post("/api/v1/auth/refresh/")
        self.assertIn(response.status_code, [400, 401])


# ===========================================================================
# 3. LogoutView Tests
# ===========================================================================


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_logout_returns_200(self):
        response = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, 200)

    def test_logout_response_body_is_detail_logout(self):
        response = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(response.data, {"detail": "logout"})

    def test_unauthenticated_logout_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, 401)

    def test_blacklisted_refresh_token_cannot_be_reused(self):
        """After logout, the refresh token must be blacklisted and unusable."""
        login_resp = self.client.post(
            "/api/v1/auth/login/", {"email": "test@example.com", "password": "pass123!"}
        )
        self.assertEqual(login_resp.status_code, 200)
        refresh_cookie = login_resp.cookies["refresh_token"].value

        # Logout — blacklists the token
        self.client.post("/api/v1/auth/logout/")

        # Attempt to reuse the blacklisted refresh token
        fresh_client = APIClient()
        fresh_client.cookies["refresh_token"] = refresh_cookie
        response = fresh_client.post("/api/v1/auth/refresh/")
        self.assertIn(
            response.status_code,
            [400, 401],
            "Blacklisted refresh token must not produce a new access token",
        )

    def test_logout_clears_access_token_cookie(self):
        """After logout, access_token cookie must be cleared (Max-Age=0 or empty value)."""
        response = self.client.post("/api/v1/auth/logout/")
        if "access_token" in response.cookies:
            self.assertEqual(response.cookies["access_token"].value, "")


# ===========================================================================
# 4. UserMeAPIView Tests
# ===========================================================================


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

    # --- GET ---

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
# 5. User Model Tests
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
        import uuid

        user = make_user()
        self.assertIsInstance(user.id, uuid.UUID)

    def test_email_must_be_unique(self):
        make_user()
        with self.assertRaises(Exception):
            make_user(username="other")  # same email, different username

    def test_username_must_be_unique(self):
        make_user()
        with self.assertRaises(Exception):
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
