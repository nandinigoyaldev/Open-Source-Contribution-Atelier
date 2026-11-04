import json
import logging
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from pywebpush import WebPushException, webpush  # type: ignore

from .models import PushSubscription
from .vapid import build_vapid_claims

logger = logging.getLogger(__name__)


def send_web_push_notification(user_id, title, message, url=None):
    """
    Sends a Web Push notification to all subscribed endpoints for a user.
    """
    subscriptions = PushSubscription.objects.filter(user_id=user_id)
    if not subscriptions.exists():
        return

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
    vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", None)

    if not vapid_private_key or not vapid_admin_email:
        # VAPID not configured
        return

    payload_data = {
        "title": title,
        "message": message,
    }
    if url:
        payload_data["url"] = url

    payload = json.dumps(payload_data)

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=build_vapid_claims(vapid_admin_email),
            )
        except WebPushException as ex:
            # If the endpoint is no longer valid (e.g. 410 Gone, or 404 Not Found),
            # remove it from the database.
            if ex.response and ex.response.status_code in [404, 410]:
                sub.delete()
            else:
                logger.warning("Web push failed for subscription %s: %s", sub.id, ex)
        except Exception as exc:
            logger.warning(
                "Unexpected error sending web push to user %s: %s", user_id, exc
            )


try:
    from celery import shared_task
except ImportError:

    def shared_task(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def decorator(func):
            return func

        return decorator


@shared_task(name="notifications.send_bulk_email")
def send_bulk_email(payload):
    """
    Sends bulk emails based on payload data.
    Supports weekly_progress_summary, badge_earned_email, comment_posted_email,
    and notification_digest templates.
    """
    if not isinstance(payload, dict):
        return

    template_id = payload.get("template_id")
    recipients = payload.get("recipients", [])
    data = payload.get("data", {})

    if not recipients:
        return

    subject = "Open Source Contribution Atelier Update"
    message = "You have an update from OSCA."
    html_message = None
    pdf_attachment = None

    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    if template_id == "weekly_progress_summary":
        username = data.get("username", "")
        subject = f"Your Weekly Progress Summary, {username} 📊"
        if data.get("xp_earned", 0) > 0:
            subject = f"Wow, {data['xp_earned']} XP this week, {username}! 🚀"
        elif data.get("current_streak", 0) > 0:
            subject = (
                f"Don't lose your {data['current_streak']}-day streak, {username}! 🔥"
            )

        from django.contrib.auth import get_user_model

        from apps.progress.services.pdf_report_service import PDFReportGenerator

        User = get_user_model()
        user_email = recipients[0] if recipients else None

        try:
            html_message = render_to_string("notifications/weekly_digest.html", data)
            message = strip_tags(html_message)
        except Exception as exc:
            logger.warning("Could not render weekly_digest.html: %s", exc)

        # Generate PDF attachment if a single user is matched
        if user_email:
            user = User.objects.filter(email=user_email).first()
            if user:
                try:
                    pdf_gen = PDFReportGenerator(user)
                    pdf_attachment = pdf_gen.generate()
                except Exception as exc:
                    logger.warning(
                        "Could not generate PDF report for %s: %s", user_email, exc
                    )

    elif template_id == "badge_earned_email":
        badge_name = data.get("badge_name", "")
        username = data.get("username", "")
        subject = "🏅 You Earned a New Badge!"
        message = (
            f"Hi {username},\n\n"
            f"Congratulations! You earned the '{badge_name}' badge.\n\n"
            "Keep up the great work!"
        )
        try:
            html_message = render_to_string(
                "notifications/badge_email.html",
                {
                    "title": f"Badge Unlocked: {badge_name}",
                    "message": f"Congratulations {username}! You earned the '{badge_name}' badge.",
                    **data,
                },
            )
        except Exception as e:
            logger.warning("Caught exception: %s", e)

    elif template_id == "comment_posted_email":
        reviewer_name = data.get("reviewer_name", "")
        username = data.get("username", "")
        feedback = data.get("feedback", "")
        subject = "👀 New Peer Review on Your Submission"
        message = (
            f"Hi {username},\n\n"
            f"{reviewer_name} just left a review on your submission:\n\n"
            f'"{feedback}"\n\n'
            "Log in to the platform to see the full details!"
        )
        try:
            html_message = render_to_string(
                "notifications/comment_email.html",
                {
                    "title": f"New review by {reviewer_name}",
                    "message": f"{reviewer_name} reviewed your submission: '{feedback}'",
                    **data,
                },
            )
        except Exception as e:
            logger.warning("Caught exception: %s", e)

    elif template_id == "notification_digest":
        freq = (
            data.get("digest_frequency", "weekly").title()
            if isinstance(data.get("digest_frequency"), str)
            else "Weekly"
        )
        subject = f"Your {freq} Notification Digest"
        try:
            html_message = render_to_string("notifications/email/digest.html", data)
            message = strip_tags(html_message)
        except Exception as exc:
            logger.warning("Could not render digest.html: %s", exc)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@atelier.dev")
    email = EmailMultiAlternatives(
        subject=subject, body=message, from_email=from_email, to=recipients
    )
    if html_message:
        email.attach_alternative(html_message, "text/html")

    if pdf_attachment:
        email.attach("OSCA_Progress_Report.pdf", pdf_attachment, "application/pdf")

    email.send(fail_silently=False)


@shared_task
def send_notification_digests():
    """
    Periodic task to send digest emails to users based on their timezone and preference.

    Builds a per-recipient payload (rendering/serialization-friendly dict context)
    for each eligible subscriber, chunks the list into batches of 50, and fans the
    emails out in parallel across worker threads using a Celery ``group``. Each
    member of the group is a ``send_bulk_email`` subtask.
    """
    import zoneinfo

    from celery import group
    from django.utils import timezone

    from .models import Notification, NotificationPreference

    prefs = NotificationPreference.objects.exclude(
        digest_frequency="none"
    ).select_related("user", "user__user_profile")

    # Build one serializable payload per eligible subscriber, chunked into batches
    # of BATCH_SIZE so we can fan out a bounded number of parallel subtasks.
    BATCH_SIZE = 50
    chunks: list[list] = []
    current_batch: list = []

    for pref in prefs:
        if not pref.digest_time:
            continue

        user = pref.user
        try:
            tz = zoneinfo.ZoneInfo(user.user_profile.timezone)
        except Exception as e:
            logger.warning("Caught exception: %s", e)
            tz = timezone.utc

        local_time = timezone.now().astimezone(tz)

        # Check if the current hour matches the user's preferred digest hour
        if local_time.hour != pref.digest_time.hour:
            continue

        # If weekly, only send on Monday (weekday() == 0)
        if pref.digest_frequency == "weekly" and local_time.weekday() != 0:
            continue

        # Fetch unread notifications
        unread_notifs = Notification.objects.filter(
            recipient=user, is_read=False
        ).order_by("-created_at")
        if not unread_notifs.exists():
            continue

        # Group notifications by type (serializable snapshot for async transport)
        grouped = {}
        for notif in unread_notifs:
            key = notif.notif_type
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(
                {
                    "title": notif.title,
                    "message": notif.message,
                    "created_at": notif.created_at,
                }
            )

        # Send Email via send_bulk_email subtask dispatched through a Celery group
        payload = {
            "template_id": "notification_digest",
            "recipients": [user.email],
            "data": {
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "id": user.id,
                },
                "digest_frequency": pref.digest_frequency,
                "grouped_notifications": grouped,
                "total_count": unread_notifs.count(),
            },
        }
        current_batch.append(send_bulk_email.s(payload))

        # Flush a full batch into the chunks list
        if len(current_batch) >= BATCH_SIZE:
            chunks.append(current_batch)
            current_batch = []

    # Flush any remaining subtasks (including the empty case, which is a no-op)
    if current_batch:
        chunks.append(current_batch)

    # Fan out each batch as a Celery group, running subtasks in parallel.
    # In eager mode (development/tests) run the group locally via `apply`
    # so no broker is required; otherwise dispatch via `apply_async`.
    eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
    for batch in chunks:
        if not batch:
            continue
        try:
            if eager:
                group(batch).apply()
            else:
                group(batch).apply_async()
        except Exception as exc:
            logger.error(
                "Failed to dispatch digest email group of %s recipients: %s",
                len(batch),
                exc,
            )


import time
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.notifications.channels import get_channel_instance, get_registered_channels
from apps.notifications.delivery import (
    MAX_ERROR_CHARS,
    MAX_RESPONSE_CHARS,
    PERMANENT,
    RATE_LIMITED,
    TRANSIENT,
    DeliveryResult,
    _status_of,
    backoff_seconds,
    classify_failure,
    normalize_result,
    truncate,
)
from apps.notifications.models import (
    Notification,
    NotificationAttempt,
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationPreference,
)
from apps.notifications.rate_limiter import ChannelRateLimiter

# A delivery that was already handed to the provider must not be sent again.
FINISHED_STATUSES = ("sent", "opened", "clicked", "bounced")


def _setting(name, default):
    return getattr(settings, name, default)


def max_attempts() -> int:
    """Tries a delivery gets before it is given up on and moved to the dead letters."""
    return max(1, int(_setting("NOTIFICATION_MAX_ATTEMPTS", 3)))


def _claim_lease() -> timedelta:
    return timedelta(seconds=int(_setting("NOTIFICATION_CLAIM_LEASE_SECONDS", 120)))


def _claim_delivery(delivery_id: int):
    """
    Take the delivery for this worker, or return None.

    The claim is one conditional UPDATE, so two workers handed the same delivery (a re-delivered
    task, a retry racing the recovery sweep) cannot both send it. A claim older than the lease is
    treated as left behind by a worker that died.
    """
    now = timezone.now()
    taken = (
        NotificationDelivery.objects.filter(id=delivery_id, status="pending")
        .filter(Q(claimed_at__isnull=True) | Q(claimed_at__lt=now - _claim_lease()))
        .update(claimed_at=now)
    )
    if not taken:
        return None
    return NotificationDelivery.objects.select_related("recipient").get(id=delivery_id)


def _can_schedule(task) -> bool:
    """False when called as a plain function or eagerly; then the recovery sweep picks it up."""
    request = getattr(task, "request", None)
    if request is None or getattr(request, "called_directly", True):
        return False
    return not _setting("CELERY_TASK_ALWAYS_EAGER", False)


def _enqueue(delivery_id: int, delay: int = 0) -> None:
    try:
        process_notification_delivery.apply_async(
            args=(delivery_id, None), countdown=delay
        )
    except Exception as exc:
        # Left pending with next_retry_at set: recover_stale_deliveries will queue it.
        logger.warning("Could not queue delivery #%s: %s", delivery_id, exc)


def _dead_letter(delivery, error: str, payload: dict) -> None:
    NotificationDeadLetter.objects.create(
        notification=delivery.notification,
        recipient=delivery.recipient,
        channel=delivery.channel,
        retry_count=delivery.retry_count,
        error_message=truncate(error, MAX_ERROR_CHARS),
        payload=payload or {},
    )


def _finish_attempt(
    attempt, started_mono, outcome, *, kind="", error="", result=None, status=None
):
    attempt.outcome = outcome
    attempt.error_class = kind
    attempt.error_message = truncate(error, MAX_ERROR_CHARS)
    attempt.finished_at = timezone.now()
    attempt.duration_ms = int((time.monotonic() - started_mono) * 1000)
    if result is not None:
        attempt.provider = result.provider
        attempt.provider_message_id = truncate(result.message_id, 255)
        attempt.status_code = result.status_code
        attempt.provider_response = _clip_response(result.response)
    if status is not None and attempt.status_code is None:
        attempt.status_code = status
    attempt.save()


def _clip_response(response) -> dict:
    """Keep provider metadata small: long strings are cut, the rest is passed through."""
    if not isinstance(response, dict):
        return {}
    clipped = {}
    for key, value in list(response.items())[:20]:
        if isinstance(value, (bool, int, float, type(None))):
            clipped[str(key)[:60]] = value
        else:
            # strings are cut, and anything that is not plain JSON is stored as text
            clipped[str(key)[:60]] = truncate(value, MAX_RESPONSE_CHARS)
    return clipped


def _skip_finished(delivery_id: int):
    """A task for a delivery that is not claimable: report what is already true about it."""
    delivery = NotificationDelivery.objects.filter(id=delivery_id).first()
    if delivery is None:
        logger.error("NotificationDelivery #%s does not exist", delivery_id)
        return False
    if delivery.status in FINISHED_STATUSES:
        NotificationAttempt.objects.create(
            delivery=delivery,
            attempt_number=delivery.attempts.count() + 1,
            outcome="skipped",
            error_message=f"Already {delivery.status}; not sent again",
            started_at=timezone.now(),
            finished_at=timezone.now(),
            duration_ms=0,
        )
        logger.info(
            "Delivery #%s is already %s, skipping.", delivery_id, delivery.status
        )
        return True
    logger.info(
        "Delivery #%s is %s or being handled by another worker, skipping.",
        delivery_id,
        delivery.status,
    )
    return False


def _fail_for_good(delivery, kind: str, error: str, payload: dict) -> None:
    delivery.status = "failed"
    delivery.error_class = kind
    delivery.error_message = truncate(error, MAX_ERROR_CHARS)
    delivery.next_retry_at = None
    delivery.claimed_at = None
    delivery.save()
    _dead_letter(delivery, error, payload)


@shared_task(bind=True, max_retries=3)
def process_notification_delivery(
    self, delivery_id: int, payload: Optional[dict] = None
):
    """
    Deliver one notification on one channel and write down what happened.

    * Idempotent: a delivery that is already sent is not sent again, and only one worker at a
      time can hold a delivery.
    * Every try is recorded in ``NotificationAttempt`` with timing and the provider's answer.
    * Failures are classified. A *permanent* one (no address, a 4xx from the provider, bad data)
      goes straight to the dead letters; a *transient* one (timeout, 5xx, 429, network) is retried
      with backoff until ``NOTIFICATION_MAX_ATTEMPTS`` tries are used.
    * Being rate limited is not a failure: the delivery is deferred without using up an attempt.
    """
    delivery = _claim_delivery(delivery_id)
    if delivery is None:
        return _skip_finished(delivery_id)

    if payload and not delivery.payload:
        delivery.payload = payload
    payload = dict(payload or delivery.payload or {})

    now = timezone.now()
    started_mono = time.monotonic()
    attempt = NotificationAttempt.objects.create(
        delivery=delivery,
        attempt_number=delivery.attempts.count() + 1,
        started_at=now,
    )
    delivery.last_attempt_at = now

    channel_id = delivery.channel
    allowed, _ = ChannelRateLimiter.is_allowed(delivery.recipient_id, channel_id)
    if not allowed:
        logger.warning(
            "Rate limit exceeded for user %s on channel %s",
            delivery.recipient_id,
            channel_id,
        )
        _finish_attempt(
            attempt,
            started_mono,
            "rate_limited",
            kind=RATE_LIMITED,
            error="Rate limit exceeded",
        )
        deferrals = delivery.attempts.filter(outcome="rate_limited").count()
        if deferrals > int(_setting("NOTIFICATION_RATE_LIMIT_MAX_DEFERRALS", 5)):
            _fail_for_good(
                delivery,
                RATE_LIMITED,
                "Rate limit exceeded",
                payload,
            )
            return False
        delay = int(_setting("NOTIFICATION_RATE_LIMIT_DELAY_SECONDS", 60))
        delivery.error_class = RATE_LIMITED
        delivery.error_message = "Rate limit exceeded"
        delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)
        delivery.claimed_at = None
        delivery.save()
        if _can_schedule(self):
            _enqueue(delivery.id, delay)
        return False

    channel_instance = get_channel_instance(channel_id)
    if not channel_instance:
        err = f"Channel '{channel_id}' is not registered."
        _finish_attempt(
            attempt, started_mono, "permanent_failure", kind=PERMANENT, error=err
        )
        _fail_for_good(delivery, PERMANENT, err, payload)
        return False

    result: Optional[DeliveryResult] = None
    failure = None
    try:
        result = normalize_result(
            channel_instance.deliver(
                delivery,
                delivery.recipient,
                payload,
            )
        )
        if not result.success:
            failure = (
                PERMANENT if result.retryable is False else TRANSIENT,
                result.error or f"Delivery failed on channel '{channel_id}'",
            )
    except Exception as exc:
        failure = (classify_failure(exc), str(exc) or exc.__class__.__name__)
        result = None
        status = _status_of(exc)
        provider = getattr(exc, "provider", "")
        response = getattr(exc, "response", None)
        if provider or status is not None or isinstance(response, dict):
            result = DeliveryResult(
                success=False,
                provider=provider,
                status_code=status,
                response=response if isinstance(response, dict) else {},
            )

    if failure is None:
        delivery.status = "sent"
        delivery.sent_at = timezone.now()
        delivery.error_message = ""
        delivery.error_class = ""
        delivery.next_retry_at = None
        delivery.claimed_at = None
        assert result is not None  # a delivery only succeeds with a result
        delivery.provider = result.provider
        delivery.provider_message_id = truncate(result.message_id, 255)
        delivery.provider_response = _clip_response(result.response)
        delivery.save()
        _finish_attempt(attempt, started_mono, "sent", result=result)
        return True

    kind, error = failure
    if result is not None:
        delivery.provider = result.provider or delivery.provider
        delivery.provider_response = _clip_response(result.response)
    delivery.retry_count += 1
    outcome = "permanent_failure" if kind == PERMANENT else "transient_failure"
    _finish_attempt(
        attempt, started_mono, outcome, kind=kind, error=error, result=result
    )

    if kind == PERMANENT or delivery.retry_count >= max_attempts():
        _fail_for_good(delivery, kind, error, payload)
        return False

    delay = backoff_seconds(delivery.retry_count)
    delivery.status = "pending"
    delivery.error_class = kind
    delivery.error_message = truncate(error, MAX_ERROR_CHARS)
    delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)
    delivery.claimed_at = None
    delivery.save()
    if _can_schedule(self):
        _enqueue(delivery.id, delay)
    return False


@shared_task
def recover_stale_deliveries(limit: int = 500):
    """
    Pick up deliveries that no worker is going to finish by itself.

    * An attempt still ``started`` after the claim lease means its worker died: it is closed as
      ``abandoned`` and counts as a failed try.
    * A pending delivery whose retry time has passed (or that was never picked up) is queued again.
    * One that has used all its tries is moved to the dead letters.

    Deliveries are handled one by one and each is queued as its own task, so one stuck or failing
    channel never holds up the others.
    """
    now = timezone.now()
    lease = _claim_lease()
    stale_after = timedelta(
        seconds=int(_setting("NOTIFICATION_STALE_AFTER_SECONDS", 300))
    )
    summary = {"abandoned": 0, "requeued": 0, "exhausted": 0}

    orphaned = list(
        NotificationAttempt.objects.filter(
            outcome="started", started_at__lt=now - lease
        )[:limit]
    )
    for attempt in orphaned:
        attempt.outcome = "abandoned"
        attempt.error_class = TRANSIENT
        attempt.error_message = "The worker stopped before the attempt finished"
        attempt.finished_at = now
        attempt.save(
            update_fields=["outcome", "error_class", "error_message", "finished_at"]
        )
        NotificationDelivery.objects.filter(
            pk=attempt.delivery_id, status="pending"
        ).update(retry_count=F("retry_count") + 1)
        summary["abandoned"] += 1

    due = (
        NotificationDelivery.objects.filter(status="pending")
        .filter(Q(claimed_at__isnull=True) | Q(claimed_at__lt=now - lease))
        .filter(
            Q(next_retry_at__lte=now)
            | Q(next_retry_at__isnull=True, created_at__lt=now - stale_after)
        )
        .select_related("recipient", "notification")
        .order_by("id")[:limit]
    )
    eager = _setting("CELERY_TASK_ALWAYS_EAGER", False)
    for delivery in due:
        if delivery.retry_count >= max_attempts():
            _fail_for_good(
                delivery,
                TRANSIENT,
                delivery.error_message or "Gave up after repeated worker failures",
                delivery.payload,
            )
            summary["exhausted"] += 1
            continue
        if eager:
            process_notification_delivery(delivery.id, None)
        else:
            _enqueue(delivery.id)
        summary["requeued"] += 1

    if any(summary.values()):
        logger.info("Notification delivery recovery: %s", summary)
    return summary


@shared_task
def purge_notification_ledger_task():
    """Periodic task: apply the retention windows to the delivery ledger."""
    from apps.notifications.retention import purge_notification_ledger

    return purge_notification_ledger()


def dispatch_notification(
    recipient,
    notif_type: str,
    title: str,
    message: str,
    meta: Optional[dict] = None,
    sender=None,
    dedupe_key: Optional[str] = None,
):
    """
    Create the notification and one delivery per enabled channel, then start delivering.

    Pass ``dedupe_key`` (see ``apps.notifications.delivery.make_dedupe_key``) to make the call
    idempotent: dispatching the same key for the same recipient again, for example because a
    signal handler or a task was retried, creates nothing new and returns the deliveries of the
    first call.
    """
    if meta is None:
        meta = {}

    from django.contrib.auth import get_user_model

    User = get_user_model()
    if isinstance(recipient, (int, str)):
        try:
            recipient = User.objects.get(id=int(recipient))
        except (ValueError, User.DoesNotExist):
            return []

    if dedupe_key:
        dedupe_key = str(dedupe_key)[:128]
        existing = list(
            NotificationDelivery.objects.filter(
                recipient=recipient, dedupe_key=dedupe_key
            )
        )
        if existing:
            logger.info(
                "Notification %s for user %s already dispatched.",
                dedupe_key,
                recipient.pk,
            )
            return existing

    pref, _ = NotificationPreference.objects.get_or_create(user=recipient)

    type_prefs = pref.channel_preferences.get(notif_type, {})
    if not type_prefs:
        type_prefs = {
            "in_app": pref.in_app_enabled,
            "email": pref.email_enabled,
            "push": True,
            "sms": False,
            "webhook": False,
            "slack": False,
        }

    registered = get_registered_channels()
    deliveries = []
    payloads = {}

    try:
        # The notification and its deliveries are written together: either all exist or none do.
        with transaction.atomic():
            notification = None
            if type_prefs.get("in_app", True):
                notification = Notification.objects.create(
                    recipient=recipient,
                    sender=sender,
                    notif_type=notif_type,
                    title=title,
                    message=message,
                    meta=meta,
                )

            payload = {
                "notif_type": notif_type,
                "title": title,
                "message": message,
                "meta": meta,
                "notification_id": notification.id if notification else None,
            }

            for channel_id in registered.keys():
                if type_prefs.get(channel_id, False) or (
                    channel_id == "in_app" and type_prefs.get("in_app", True)
                ):
                    delivery = NotificationDelivery.objects.create(
                        notification=notification,
                        recipient=recipient,
                        channel=channel_id,
                        status="pending",
                        meta=meta,
                        dedupe_key=dedupe_key or None,
                        payload=payload,
                    )
                    deliveries.append(delivery)
                    payloads[delivery.id] = payload
    except IntegrityError:
        # Another worker dispatched the same event between our check and our insert.
        if dedupe_key:
            return list(
                NotificationDelivery.objects.filter(
                    recipient=recipient, dedupe_key=dedupe_key
                )
            )
        raise

    for delivery in deliveries:
        payload = payloads[delivery.id]
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", True) or getattr(
            settings, "TESTING", False
        ):
            try:
                process_notification_delivery(delivery.id, payload)
                delivery.refresh_from_db()
            except Exception as exc:
                logger.error(
                    "Error processing delivery #%s synchronously: %s",
                    delivery.id,
                    exc,
                )
        else:
            try:
                process_notification_delivery.delay(delivery.id, payload)
            except Exception as e:
                logger.warning("Caught exception: %s", e)
                process_notification_delivery(delivery.id, payload)
                delivery.refresh_from_db()

    return deliveries


from .webhooks import dispatch_outgoing_webhook


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
    rate_limit="100/m",
)
def deliver_webhook_event(self, url: str, payload: dict, secret: str):
    """
    Celery background worker process that handles outbound event notifications.
    Dynamically increments state counters across automatic retry execution windows.
    """
    # Extract structural retry counter context (Defaults to 0 on initial task run)
    current_retry_count = self.request.retries
    attempt_number = current_retry_count + 1

    logger.info(
        f"[WEBHOOK INITIATED] Target URL: {url} | Attempt Sequence: {attempt_number}"
    )

    try:
        dispatch_outgoing_webhook(
            url=url, payload=payload, secret=secret, attempt_number=attempt_number
        )
    except Exception as exc:
        logger.warning(
            f"[RETRY CALLBACK ENGAGED] Webhook attempt {attempt_number} failed. Re-queueing task."
        )
        # Re-raise error to propagate structural Celery autoretry handlers cleanly
        raise exc
