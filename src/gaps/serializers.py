from rest_framework import serializers

from .models import TrackedGap


class AnomalySerializer(serializers.Serializer):
    """Validates the raw anomaly payload (shaped like the "gap" object in
    golden_dataset/examples.jsonl) before it's handed to route_anomaly.

    Only checks that the fields route_anomaly reads are present as
    non-empty strings — domain validation (valid gap_type/account/severity)
    stays in routing.py, the single source of truth for that logic.
    """

    gap_id = serializers.CharField()
    building = serializers.CharField()
    building_id = serializers.CharField()
    account = serializers.CharField()
    gap_type = serializers.CharField()
    detail = serializers.CharField()
    severity = serializers.CharField()


class TrackedGapSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackedGap
        fields = [
            "id",
            "gap_id",
            "building",
            "building_id",
            "account",
            "gap_type",
            "detail",
            "owner_role",
            "owner_name",
            "severity",
            "status",
            "draft",
            "is_grounded",
            "groundedness_violations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
