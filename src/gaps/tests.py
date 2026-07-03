import json
from pathlib import Path

from django.test import SimpleTestCase

from .routing import UnroutableGap, route_anomaly

# golden_dataset/ lives at the repo root, two levels above src/gaps/.
EXAMPLES_PATH = Path(__file__).resolve().parent.parent.parent / "golden_dataset" / "examples.jsonl"


def load_examples():
    """Load golden_dataset/examples.jsonl as a list of {id, gap, labels} records."""
    with EXAMPLES_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def make_anomaly(**overrides):
    """A minimal valid anomaly dict (missing_utility_bill / Nuveen), for
    tests that isolate one field at a time rather than using a full
    dataset record.
    """
    anomaly = {
        "gap_id": "G-0000",
        "building": "Test Building",
        "building_id": "BLD-000",
        "account": "Nuveen — Affordable Housing Fund II",
        "gap_type": "missing_utility_bill",
        "detail": "Test detail.",
        "severity": "high",
    }
    anomaly.update(overrides)
    return anomaly


class RouteAnomalyHappyPathTests(SimpleTestCase):
    """route_anomaly on real anomalies should reproduce the golden owner
    and severity for every record in golden_dataset/examples.jsonl — this
    is the routing logic's actual acceptance test.
    """

    def test_every_golden_example_routes_to_its_recorded_owner_and_severity(self):
        for example in load_examples():
            gap = example["gap"]
            with self.subTest(example_id=example["id"]):
                routed = route_anomaly(gap)
                self.assertEqual(routed["owner_role"], gap["owner_role"])
                self.assertEqual(routed["owner_name"], gap["owner_name"])
                self.assertEqual(routed["severity"], gap["severity"])

    def test_passthrough_fields_are_carried_unchanged(self):
        gap = load_examples()[0]["gap"]
        routed = route_anomaly(gap)
        self.assertEqual(routed["gap_id"], gap["gap_id"])
        self.assertEqual(routed["building"], gap["building"])
        self.assertEqual(routed["building_id"], gap["building_id"])
        self.assertEqual(routed["account"], gap["account"])
        self.assertEqual(routed["gap_type"], gap["gap_type"])
        self.assertEqual(routed["detail"], gap["detail"])

    def test_routed_record_always_starts_as_new(self):
        gap = load_examples()[0]["gap"]
        routed = route_anomaly(gap)
        self.assertEqual(routed["status"], "new")


class OwnerAssignmentTests(SimpleTestCase):
    """owner_role is a direct function of gap_type; owner_name is a fixed
    roster lookup (per-account for property managers, a single person for
    the other two roles).
    """

    def test_missing_utility_bill_routes_to_property_manager(self):
        routed = route_anomaly(make_anomaly(gap_type="missing_utility_bill"))
        self.assertEqual(routed["owner_role"], "property_manager")

    def test_unmatched_meter_routes_to_asset_manager(self):
        routed = route_anomaly(make_anomaly(gap_type="unmatched_meter"))
        self.assertEqual(routed["owner_role"], "asset_manager")
        self.assertEqual(routed["owner_name"], "Priya Raman")

    def test_incomplete_equipment_inventory_routes_to_building_engineer(self):
        routed = route_anomaly(make_anomaly(gap_type="incomplete_equipment_inventory"))
        self.assertEqual(routed["owner_role"], "building_engineer")
        self.assertEqual(routed["owner_name"], "Marcus Feld")

    def test_tenant_owner_paid_ambiguity_routes_to_asset_manager(self):
        routed = route_anomaly(make_anomaly(gap_type="tenant_owner_paid_ambiguity"))
        self.assertEqual(routed["owner_role"], "asset_manager")
        self.assertEqual(routed["owner_name"], "Priya Raman")

    def test_property_manager_name_resolves_by_account(self):
        cases = {
            "Nuveen — Affordable Housing Fund II": "Dana Okafor",
            "LaSalle — Value-Add Fund III": "Tomás Herrera",
            "Topview Investments": "Benjamin White",
            "Beacon Capital — Core Fund": "Sarah Whitfield",
        }
        for account, expected_name in cases.items():
            with self.subTest(account=account):
                routed = route_anomaly(make_anomaly(account=account))
                self.assertEqual(routed["owner_name"], expected_name)


class SeverityNormalizationTests(SimpleTestCase):
    """severity is normalized (trimmed, lowercased) from whatever the raw
    anomaly provides — never inferred from gap_type or detail text.
    """

    def test_uppercase_severity_is_lowercased(self):
        routed = route_anomaly(make_anomaly(severity="HIGH"))
        self.assertEqual(routed["severity"], "high")

    def test_mixed_case_and_whitespace_is_cleaned(self):
        routed = route_anomaly(make_anomaly(severity="  Medium  "))
        self.assertEqual(routed["severity"], "medium")

    def test_already_normalized_value_passes_through(self):
        routed = route_anomaly(make_anomaly(severity="low"))
        self.assertEqual(routed["severity"], "low")


class UnroutableGapTests(SimpleTestCase):
    """The routing function must fail loudly rather than guess whenever the
    input doesn't give it enough to route confidently. This is the most
    important behavior in this module: a silent default here would mean
    inventing an owner or a severity we have no basis for.
    """

    def test_missing_severity_raises(self):
        anomaly = make_anomaly()
        del anomaly["severity"]
        with self.assertRaises(UnroutableGap):
            route_anomaly(anomaly)

    def test_invalid_severity_raises(self):
        with self.assertRaises(UnroutableGap):
            route_anomaly(make_anomaly(severity="urgent"))

    def test_unmapped_gap_type_raises(self):
        with self.assertRaises(UnroutableGap):
            route_anomaly(make_anomaly(gap_type="roof_leak"))

    def test_unknown_account_raises(self):
        with self.assertRaises(UnroutableGap):
            route_anomaly(make_anomaly(
                gap_type="missing_utility_bill",
                account="Some Unrostered Fund",
            ))
