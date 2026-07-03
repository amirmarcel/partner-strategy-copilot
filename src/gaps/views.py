from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .drafting import draft_outreach
from .guardrails import check_groundedness
from .models import TrackedGap
from .routing import UnroutableGap, route_anomaly
from .serializers import AnomalySerializer, TrackedGapSerializer


class GapListCreateView(APIView):
    """GET lists tracked gaps. POST ingests one raw anomaly and runs the
    full synchronous pipeline: route -> create -> draft -> guardrail.
    """

    def get(self, request):
        gaps = TrackedGap.objects.order_by("-created_at")
        return Response(TrackedGapSerializer(gaps, many=True).data)

    def post(self, request):
        anomaly_serializer = AnomalySerializer(data=request.data)
        anomaly_serializer.is_valid(raise_exception=True)
        anomaly = anomaly_serializer.validated_data

        try:
            routed = route_anomaly(anomaly)
        except UnroutableGap as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        gap, created = TrackedGap.objects.get_or_create(
            gap_id=routed["gap_id"], defaults=routed
        )
        if not created:
            return Response(
                {"detail": f"gap_id {routed['gap_id']!r} is already tracked"},
                status=status.HTTP_409_CONFLICT,
            )

        draft = draft_outreach(routed)
        guardrail = check_groundedness(draft, routed)

        # AGENTS.md Rule 2: an ungrounded draft must be rejected, not shown.
        # The gap record still exists (status stays "new") so a human can
        # see the routing succeeded and the draft attempt failed guardrail,
        # but the draft text itself is never persisted or returned.
        gap.is_grounded = guardrail.is_grounded
        gap.groundedness_violations = guardrail.violations
        if guardrail.is_grounded:
            gap.draft = draft
            gap.status = TrackedGap.Status.DRAFTED
        gap.save()

        return Response(TrackedGapSerializer(gap).data, status=status.HTTP_201_CREATED)


class GapDetailView(APIView):
    def get(self, request, pk):
        gap = get_object_or_404(TrackedGap, pk=pk)
        return Response(TrackedGapSerializer(gap).data)


class GapApproveView(APIView):
    """Hard Rule 3's human-approval gate: drafted -> approved only.

    Approved is the terminal state this tool produces; sending is out of
    scope (see AGENTS.md / roadmap).
    """

    def post(self, request, pk):
        gap = get_object_or_404(TrackedGap, pk=pk)
        if gap.status != TrackedGap.Status.DRAFTED:
            return Response(
                {
                    "detail": (
                        f"cannot approve gap in status {gap.status!r}; "
                        "only a gap in status 'drafted' may be approved"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        gap.status = TrackedGap.Status.APPROVED
        gap.save(update_fields=["status", "updated_at"])
        return Response(TrackedGapSerializer(gap).data)
