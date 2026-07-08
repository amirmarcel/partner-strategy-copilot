"""Tests for the DRF API layer (src/gaps/views.py): ingest, approve,
list/retrieve. Distinct from tests.py (routing unit tests, no DB) and
evaluations/ (non-deterministic draft quality) — these exercise the HTTP
endpoints against a real (sqlite, in-memory during tests) database, so they
use TestCase rather than SimpleTestCase.

No network calls: every test that reaches draft_outreach patches
gaps.drafting.get_provider with a FakeProvider, per AGENTS.md Rule 5 (the
LLM is only ever reached through the provider interface, which makes it
trivial to swap in tests).
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import TrackedGap

VALID_ANOMALY = {
    "gap_id": "G-4471",
    "building": "Maple Court Apartments",
    "building_id": "BLD-129",
    "account": "Northwind — Affordable Housing Fund II",
    "gap_type": "missing_utility_bill",
    "detail": "No electricity bill on file for 2025-Q3 (Jul-Sep).",
    "severity": "high",
}


class FakeProvider:
    """Stands in for AnthropicProvider (same complete() surface). Returns a
    fixed, caller-supplied string instead of calling the Anthropic API.
    """

    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


def patch_provider(response: str):
    """draft_outreach() falls back to gaps.llm.get_provider() when called
    with no provider argument (which is how the view calls it), so patching
    it at the import site in drafting.py is the seam the view actually
    exercises.
    """
    return patch("gaps.drafting.get_provider", return_value=FakeProvider(response))


class IngestEndpointTests(TestCase):
    """POST /api/gaps/"""

    def setUp(self):
        self.client = APIClient()

    def test_successful_ingest_creates_drafted_gap(self):
        grounded_draft = (
            "Dana,\n\nWe're missing the Q3 2025 electricity bill for Maple "
            "Court Apartments (Gap ID G-4471). Could you send it over?\n\nThanks."
        )
        with patch_provider(grounded_draft):
            response = self.client.post(
                "/api/gaps/", VALID_ANOMALY, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrackedGap.objects.count(), 1)

        gap = TrackedGap.objects.get(gap_id="G-4471")
        self.assertEqual(gap.status, TrackedGap.Status.DRAFTED)
        self.assertEqual(gap.draft, grounded_draft)
        self.assertTrue(gap.is_grounded)
        self.assertEqual(gap.groundedness_violations, [])

        # response body mirrors DB state
        self.assertEqual(response.data["status"], "drafted")
        self.assertEqual(response.data["draft"], grounded_draft)

    def test_unroutable_gap_type_returns_400_and_creates_no_row(self):
        anomaly = {**VALID_ANOMALY, "gap_type": "roof_leak"}

        response = self.client.post("/api/gaps/", anomaly, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertEqual(TrackedGap.objects.count(), 0)

    def test_unroutable_unknown_account_returns_400_and_creates_no_row(self):
        anomaly = {**VALID_ANOMALY, "account": "Some Unrostered Fund"}

        response = self.client.post("/api/gaps/", anomaly, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TrackedGap.objects.count(), 0)

    def test_duplicate_gap_id_returns_409_and_does_not_create_second_row(self):
        with patch_provider("some draft mentioning G-4471"):
            first = self.client.post("/api/gaps/", VALID_ANOMALY, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post("/api/gaps/", VALID_ANOMALY, format="json")

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(TrackedGap.objects.count(), 1)

    def test_missing_fields_returns_400_with_per_field_errors(self):
        response = self.client.post("/api/gaps/", {"gap_id": "G-1"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ["building", "building_id", "account", "gap_type", "detail", "severity"]:
            self.assertIn(field, response.data)
        self.assertEqual(TrackedGap.objects.count(), 0)

    def test_ungrounded_draft_is_created_but_not_promoted_to_drafted(self):
        """The important path: the draft references a foreign gap ID
        (G-9999, not G-4471), so check_groundedness must fail it. Per
        AGENTS.md Rule 2 the draft is rejected, not shown — the row exists
        (routing succeeded) but stays "new" with no draft text persisted.
        """
        ungrounded_draft = (
            "See also G-9999 for related context on this account.\n\n"
            "Please send the missing bill."
        )
        with patch_provider(ungrounded_draft):
            response = self.client.post(
                "/api/gaps/", VALID_ANOMALY, format="json"
            )

        # the record is still created — routing succeeded, only the draft
        # attempt failed the guardrail
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrackedGap.objects.count(), 1)

        gap = TrackedGap.objects.get(gap_id="G-4471")
        self.assertEqual(gap.status, TrackedGap.Status.NEW)
        self.assertEqual(gap.draft, "")
        self.assertFalse(gap.is_grounded)
        self.assertTrue(gap.groundedness_violations)
        self.assertIn("G-9999", gap.groundedness_violations[0])

        # response body must not leak the rejected draft text either
        self.assertEqual(response.data["draft"], "")
        self.assertEqual(response.data["status"], "new")


class ApproveEndpointTests(TestCase):
    """POST /api/gaps/{id}/approve/ — Hard Rule 3's human-approval gate."""

    def setUp(self):
        self.client = APIClient()

    def _make_gap(self, status_value):
        return TrackedGap.objects.create(
            gap_id="G-4471",
            building="Maple Court Apartments",
            building_id="BLD-129",
            account="Northwind — Affordable Housing Fund II",
            gap_type="missing_utility_bill",
            detail="No electricity bill on file for 2025-Q3 (Jul-Sep).",
            owner_role="property_manager",
            owner_name="Dana Okafor",
            severity="high",
            status=status_value,
            draft="Dana, could you send the Q3 2025 electricity bill?",
        )

    def test_approving_a_drafted_gap_succeeds(self):
        gap = self._make_gap(TrackedGap.Status.DRAFTED)

        response = self.client.post(f"/api/gaps/{gap.pk}/approve/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "approved")
        gap.refresh_from_db()
        self.assertEqual(gap.status, TrackedGap.Status.APPROVED)

    def test_approving_a_new_gap_is_rejected(self):
        gap = self._make_gap(TrackedGap.Status.NEW)

        response = self.client.post(f"/api/gaps/{gap.pk}/approve/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        gap.refresh_from_db()
        self.assertEqual(gap.status, TrackedGap.Status.NEW)

    def test_approving_an_already_approved_gap_is_rejected(self):
        gap = self._make_gap(TrackedGap.Status.APPROVED)

        response = self.client.post(f"/api/gaps/{gap.pk}/approve/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        gap.refresh_from_db()
        self.assertEqual(gap.status, TrackedGap.Status.APPROVED)

    def test_approving_unknown_gap_returns_404(self):
        response = self.client.post("/api/gaps/999/approve/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ListAndRetrieveEndpointTests(TestCase):
    """GET /api/gaps/ and GET /api/gaps/{id}/"""

    def setUp(self):
        self.client = APIClient()
        self.gap1 = TrackedGap.objects.create(
            gap_id="G-4471",
            building="Maple Court Apartments",
            building_id="BLD-129",
            account="Northwind — Affordable Housing Fund II",
            gap_type="missing_utility_bill",
            detail="No electricity bill on file for 2025-Q3.",
            owner_role="property_manager",
            owner_name="Dana Okafor",
            severity="high",
            status=TrackedGap.Status.DRAFTED,
            draft="Dana, could you send the bill?",
        )
        self.gap2 = TrackedGap.objects.create(
            gap_id="G-5012",
            building="Riverside Tower",
            building_id="BLD-088",
            account="Northwind — Affordable Housing Fund II",
            gap_type="unmatched_meter",
            detail="Meter M-22 not matched to any known space.",
            owner_role="asset_manager",
            owner_name="Priya Raman",
            severity="medium",
            status=TrackedGap.Status.NEW,
        )

    def test_list_returns_all_tracked_gaps(self):
        response = self.client.get("/api/gaps/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_gap_ids = {gap["gap_id"] for gap in response.data}
        self.assertEqual(returned_gap_ids, {"G-4471", "G-5012"})

    def test_retrieve_returns_the_matching_gap(self):
        response = self.client.get(f"/api/gaps/{self.gap2.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["gap_id"], "G-5012")
        self.assertEqual(response.data["owner_name"], "Priya Raman")

    def test_retrieve_unknown_gap_returns_404(self):
        response = self.client.get("/api/gaps/999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
