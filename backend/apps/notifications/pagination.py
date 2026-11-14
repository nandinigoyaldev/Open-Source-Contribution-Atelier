"""Forward-only, signed keyset cursors for notification history."""

from django.core import signing
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import BasePagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class NotificationCursorPagination(BasePagination):
    page_size = 20
    max_page_size = 100
    cursor_salt = "notifications.history.cursor.v1"

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        try:
            size = int(request.query_params.get("page_size", self.page_size))
            if size < 1:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError({"page_size": "Use a positive integer."})
        size = min(size, self.max_page_size)

        token = request.query_params.get("cursor")
        if "cursor" in request.query_params:
            created_at, pk = self.decode_cursor(token, request.user.pk)
            queryset = queryset.filter(
                Q(created_at__lt=created_at) | Q(created_at=created_at, pk__lt=pk)
            )

        # Do not use OFFSET, a total COUNT, or require the boundary row to exist.
        rows = list(queryset.order_by("-created_at", "-pk")[: size + 1])
        page = rows[:size]
        self.next_cursor = None
        if len(rows) > size:
            last = page[-1]
            self.next_cursor = signing.dumps(
                {
                    "v": 1,
                    "user": str(request.user.pk),
                    "created_at": last.created_at.isoformat(),
                    "pk": last.pk,
                },
                salt=self.cursor_salt,
            )
        return page

    def decode_cursor(self, token, user_id):
        try:
            if not isinstance(token, str) or not token or len(token) > 2048:
                raise ValueError
            payload = signing.loads(token, salt=self.cursor_salt)
            if (
                not isinstance(payload, dict)
                or payload.get("v") != 1
                or payload.get("user") != str(user_id)
                or type(payload.get("pk")) is not int
                or not 0 < payload["pk"] <= 9223372036854775807
                or not isinstance(payload.get("created_at"), str)
                or len(payload["created_at"]) > 64
            ):
                raise ValueError
            created_at = parse_datetime(payload["created_at"])
            if created_at is None or timezone.is_naive(created_at):
                raise ValueError
            return created_at, payload["pk"]
        except (signing.BadSignature, ValueError, TypeError, OverflowError):
            raise ValidationError(
                {"cursor": "Invalid notification cursor. Restart from the first page."}
            )

    def get_paginated_response(self, data):
        next_url = (
            replace_query_param(
                self.request.build_absolute_uri(), "cursor", self.next_cursor
            )
            if self.next_cursor
            else None
        )
        return Response(
            {
                "next": next_url,
                "previous": None,
                "next_cursor": self.next_cursor,
                "results": data,
            }
        )
