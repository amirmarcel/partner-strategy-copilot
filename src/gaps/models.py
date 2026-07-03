from django.db import models


class TrackedGap(models.Model):
    """A single gap from an anomaly report, routed and tracked to resolution."""

    class GapType(models.TextChoices):
        MISSING_UTILITY_BILL = "missing_utility_bill", "Missing utility bill"
        UNMATCHED_METER = "unmatched_meter", "Unmatched meter"
        INCOMPLETE_EQUIPMENT_INVENTORY = (
            "incomplete_equipment_inventory",
            "Incomplete equipment inventory",
        )
        TENANT_OWNER_PAID_AMBIGUITY = (
            "tenant_owner_paid_ambiguity",
            "Tenant/owner paid ambiguity",
        )

    class OwnerRole(models.TextChoices):
        PROPERTY_MANAGER = "property_manager", "Property manager"
        ASSET_MANAGER = "asset_manager", "Asset manager"
        BUILDING_ENGINEER = "building_engineer", "Building engineer"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        NEW = "new", "New"
        DRAFTED = "drafted", "Drafted"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent"
        RESOLVED = "resolved", "Resolved"

    gap_id = models.CharField(max_length=32, unique=True)
    building = models.CharField(max_length=255)
    building_id = models.CharField(max_length=32, db_index=True)
    account = models.CharField(max_length=255)
    gap_type = models.CharField(max_length=64, choices=GapType.choices)
    detail = models.TextField()
    owner_role = models.CharField(max_length=32, choices=OwnerRole.choices)
    owner_name = models.CharField(max_length=255)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.NEW
    )
    draft = models.TextField(blank=True, default="")
    is_grounded = models.BooleanField(null=True, default=None)
    groundedness_violations = models.JSONField(blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.gap_id} ({self.status})"
