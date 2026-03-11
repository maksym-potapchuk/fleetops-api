"""
Fleet Management Serializer Tests
==================================
Covers: AssignRegulationSerializer validation.
"""

from django.test import TestCase

from fleet_management.serializers import AssignRegulationSerializer

from .helpers import make_item, make_schema, make_user


class AssignRegulationSerializerTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.schema = make_schema(title="Basic Regulation", user=self.user)
        self.item1 = make_item(self.schema, title="Oil Change", every_km=10_000)
        self.item2 = make_item(self.schema, title="Air Filter", every_km=20_000)
        self.item3 = make_item(self.schema, title="Tires", every_km=50_000)

    def _validate(self, data):
        s = AssignRegulationSerializer(data=data)
        s.is_valid()
        return s

    def test_valid_payload_with_all_items_is_accepted(self):
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": 0},
                    {"item_id": self.item2.id, "last_done_km": 5_000},
                    {"item_id": self.item3.id, "last_done_km": 10_000},
                ],
            }
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_partial_schema_items_accepted(self):
        """Partial submission (not all schema items) is now allowed."""
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": 0},
                ],
            }
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_item_from_foreign_schema_fails_validation(self):
        """Items not belonging to the given schema must be rejected."""
        schema2 = make_schema(title="Schema 2")
        foreign_item = make_item(schema2, title="Brakes", every_km=30_000)
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": 0},
                    {"item_id": self.item2.id, "last_done_km": 0},
                    {"item_id": self.item3.id, "last_done_km": 0},
                    {"item_id": foreign_item.id, "last_done_km": 0},
                ],
            }
        )
        self.assertFalse(s.is_valid())
        self.assertIn("do not belong to schema", str(s.errors))

    def test_nonexistent_schema_id_fails_validation(self):
        s = self._validate({"schema_id": 99_999, "entries": []})
        self.assertFalse(s.is_valid())
        self.assertIn("Schema 99999 does not exist", str(s.errors))

    def test_nonexistent_item_id_fails_validation(self):
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [{"item_id": 99_999, "last_done_km": 0}],
            }
        )
        self.assertFalse(s.is_valid())
        self.assertIn("does not exist", str(s.errors))

    def test_negative_last_done_km_fails_validation(self):
        """last_done_km has min_value=0 in RegulationEntryInitialSerializer."""
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": -100},
                    {"item_id": self.item2.id, "last_done_km": 0},
                    {"item_id": self.item3.id, "last_done_km": 0},
                ],
            }
        )
        self.assertFalse(s.is_valid(), "Negative km must be rejected by the serializer")

    def test_empty_entries_when_schema_has_items_fails(self):
        """Providing no entries when the schema has items must be rejected."""
        s = self._validate({"schema_id": self.schema.id, "entries": []})
        self.assertFalse(s.is_valid(), "All schema items must be provided")

    def test_zero_last_done_km_is_valid(self):
        """km=0 is a legitimate starting point."""
        s = self._validate(
            {
                "schema_id": self.schema.id,
                "entries": [
                    {"item_id": self.item1.id, "last_done_km": 0},
                    {"item_id": self.item2.id, "last_done_km": 0},
                    {"item_id": self.item3.id, "last_done_km": 0},
                ],
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
