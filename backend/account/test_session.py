"""
Account Session & Cookie Tests
===============================
Covers: remember_me behavior, unset-session, token rotation across refresh,
logout cookie cleanup.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User


def make_user(email="sess@example.com", password="pass123!", username="sessuser"):
    return User.objects.create_user(email=email, password=password, username=username)


class RememberMeCookieTest(TestCase):
    LOGIN_URL = "/api/v1/auth/login/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def _login(self, remember_me=None):
        payload = {"email": "sess@example.com", "password": "pass123!"}
        if remember_me is not None:
            payload["remember_me"] = remember_me
        return self.client.post(self.LOGIN_URL, payload, format="json")

    def test_remember_me_true_sets_persistent_refresh_cookie(self):
        response = self._login(remember_me=True)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get("refresh_token")
        self.assertIsNotNone(cookie)
        self.assertIsNotNone(cookie["max-age"])
        self.assertGreater(int(cookie["max-age"]), 0)

    def test_remember_me_false_sets_session_refresh_cookie(self):
        response = self._login(remember_me=False)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get("refresh_token")
        self.assertIsNotNone(cookie)
        # Session cookie: max-age is empty string (not set)
        self.assertIn(cookie["max-age"], ("", 0))

    def test_login_without_remember_me_defaults_to_session_cookie(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get("refresh_token")
        self.assertIsNotNone(cookie)
        self.assertIn(cookie["max-age"], ("", 0))

    def test_remember_me_cookie_stored_with_correct_value(self):
        response = self._login(remember_me=True)
        rm_cookie = response.cookies.get("remember_me")
        self.assertIsNotNone(rm_cookie)
        self.assertEqual(rm_cookie.value, "1")

        # Now login without remember_me
        client2 = APIClient()
        response2 = client2.post(
            self.LOGIN_URL,
            {"email": "sess@example.com", "password": "pass123!", "remember_me": False},
            format="json",
        )
        rm_cookie2 = response2.cookies.get("remember_me")
        self.assertEqual(rm_cookie2.value, "0")

    def test_access_token_always_gets_max_age(self):
        """Access token max_age is always set regardless of remember_me."""
        response = self._login(remember_me=False)
        cookie = response.cookies.get("access_token")
        self.assertIsNotNone(cookie)
        self.assertGreater(int(cookie["max-age"]), 0)


class UnsetSessionTest(TestCase):
    URL = "/api/v1/auth/unset-session/"

    def test_returns_200_without_authentication(self):
        client = APIClient()
        response = client.post(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "session cleared")

    def test_clears_all_auth_cookies(self):
        client = APIClient()
        response = client.post(self.URL)
        self.assertEqual(response.status_code, 200)
        for cookie_name in ("access_token", "refresh_token", "remember_me"):
            cookie = response.cookies.get(cookie_name)
            self.assertIsNotNone(cookie, f"{cookie_name} should be in response cookies")
            # Deleted cookies have max-age=0 and empty value
            self.assertEqual(int(cookie["max-age"]), 0)


class TokenRotationTest(TestCase):
    LOGIN_URL = "/api/v1/auth/login/"
    REFRESH_URL = "/api/v1/auth/refresh/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_refresh_rotates_token_and_updates_cookie(self):
        """After refresh, the cookie must contain the new rotated token."""
        login_resp = self.client.post(
            self.LOGIN_URL,
            {"email": "sess@example.com", "password": "pass123!"},
            format="json",
        )
        old_refresh = login_resp.cookies["refresh_token"].value

        refresh_resp = self.client.post(self.REFRESH_URL)
        self.assertEqual(refresh_resp.status_code, 200)
        new_refresh = refresh_resp.cookies.get("refresh_token")
        self.assertIsNotNone(new_refresh)
        self.assertNotEqual(new_refresh.value, old_refresh)

    def test_second_refresh_succeeds_after_rotation(self):
        """Chain two refresh calls — both must succeed (rotated token used)."""
        self.client.post(
            self.LOGIN_URL,
            {"email": "sess@example.com", "password": "pass123!"},
            format="json",
        )
        # First refresh
        resp1 = self.client.post(self.REFRESH_URL)
        self.assertEqual(resp1.status_code, 200)

        # Update cookie with rotated token
        self.client.cookies["refresh_token"] = resp1.cookies["refresh_token"].value

        # Second refresh
        resp2 = self.client.post(self.REFRESH_URL)
        self.assertEqual(resp2.status_code, 200)


class LogoutCookieCleanupTest(TestCase):
    LOGIN_URL = "/api/v1/auth/login/"
    LOGOUT_URL = "/api/v1/auth/logout/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_logout_clears_remember_me_cookie(self):
        self.client.post(
            self.LOGIN_URL,
            {"email": "sess@example.com", "password": "pass123!", "remember_me": True},
            format="json",
        )
        response = self.client.post(self.LOGOUT_URL)
        self.assertEqual(response.status_code, 200)
        rm = response.cookies.get("remember_me")
        self.assertIsNotNone(rm)
        self.assertEqual(int(rm["max-age"]), 0)
