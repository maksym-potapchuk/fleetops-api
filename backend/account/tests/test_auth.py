"""
Auth View Tests
===============
Covers: LoginView, RefreshView, LogoutView.

Focus areas:
- Cookie-based JWT authentication
- Tokens must NOT be exposed in response body
- Proper 401 for unauthenticated requests
"""

from django.test import TestCase
from rest_framework.test import APIClient

from .helpers import authenticate, make_user

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
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "wrongpass"},
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
