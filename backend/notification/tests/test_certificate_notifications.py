"""
Certificate Notification Tests
==============================
Covers: temporary certificate expiry checks, permanent certificates ignored,
preferences integration, dedup, and run_all aggregation.
"""

from datetime import date, timedelta

from django.test import TestCase

from notification.constants import NotificationType
from notification.models import Notification, NotificationPreferences
from notification.services import (
    check_all_scheduled_notifications,
    check_certificate_notifications,
)
from vehicle.models import CertificateType, RegistrationCertificate

from .helpers import make_user, make_vehicle


class CheckCertificateNotificationsTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def _make_cert(self, valid_until, type_=CertificateType.TEMPORARY, **extra):
        return RegistrationCertificate.objects.create(
            vehicle=self.vehicle,
            certificate_type=type_,
            issued_at=date.today() - timedelta(days=10),
            valid_until=valid_until,
            is_active=True,
            created_by=self.user,
            **extra,
        )

    def test_creates_expiring_notification_at_threshold(self):
        self._make_cert(date.today() + timedelta(days=3))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.CERTIFICATE_EXPIRING)
        self.assertEqual(created[0].payload["days_remaining"], 3)

    def test_no_notification_when_far_from_expiry(self):
        # Window is 30 days for temporary certs; 60 days out → no reminder.
        self._make_cert(date.today() + timedelta(days=60))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 0)

    def test_weekly_reminder_within_30_days(self):
        # 15 days out is inside the weekly-reminder window — first reminder fires.
        self._make_cert(date.today() + timedelta(days=15))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.CERTIFICATE_EXPIRING)
        self.assertEqual(created[0].payload["reminder_number"], 0)

    def test_creates_expired_notification_when_overdue(self):
        self._make_cert(date.today() - timedelta(days=2))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.CERTIFICATE_EXPIRED)
        self.assertEqual(created[0].payload["overdue_days"], 2)

    def test_permanent_certificate_is_ignored(self):
        self._make_cert(
            date.today() - timedelta(days=2),
            type_=CertificateType.PERMANENT,
        )
        created = check_certificate_notifications()
        self.assertEqual(len(created), 0)

    def test_inactive_certificate_is_ignored(self):
        cert = self._make_cert(date.today() + timedelta(days=3))
        cert.is_active = False
        cert.save()
        created = check_certificate_notifications()
        self.assertEqual(len(created), 0)

    def test_certificate_disabled_in_preferences_skips_check(self):
        NotificationPreferences.objects.create(
            user=self.user, certificate_enabled=False
        )
        self._make_cert(date.today() + timedelta(days=3))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 0)

    def test_dedup_prevents_duplicate_expiring_for_same_day(self):
        self._make_cert(date.today() + timedelta(days=3))
        check_certificate_notifications()
        created_again = check_certificate_notifications()
        self.assertEqual(len(created_again), 0)
        self.assertEqual(
            Notification.objects.filter(
                type=NotificationType.CERTIFICATE_EXPIRING
            ).count(),
            1,
        )

    def test_archived_vehicle_is_ignored(self):
        self.vehicle.is_archived = True
        self.vehicle.save()
        self._make_cert(date.today() + timedelta(days=3))
        created = check_certificate_notifications()
        self.assertEqual(len(created), 0)

    def test_run_all_includes_certificates(self):
        self._make_cert(date.today() + timedelta(days=1))
        result = check_all_scheduled_notifications()
        self.assertIn("certificates", result)
        self.assertEqual(result["certificates"], 1)
