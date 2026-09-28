from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify


class EventQuerySet(models.QuerySet):
    def upcoming(self):
        now = timezone.now()
        return self.filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))

    def published(self):
        return self.filter(is_published=True)


class Event(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events"
    )
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=160)
    city = models.CharField(max_length=80)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:120] or "event"
            slug = base
            while Event.objects.filter(slug=slug).exists():
                slug = f"{base}-{get_random_string(4).lower()}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def has_ended(self):
        return (self.ends_at or self.starts_at) < timezone.now()

    def __str__(self):
        return self.title


class TicketType(models.Model):
    """A tier of tickets for an event, e.g. "Regular" or "VIP".

    `price` is stored in kobo (₦1 = 100 kobo) — Paystack's unit — so money is
    never a float. `reserved` counts tickets that are sold *or* held by an
    unpaid order, which is what stops overselling.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    price = models.PositiveIntegerField(help_text="In kobo. 0 means free.")
    quantity = models.PositiveIntegerField()
    reserved = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["price", "id"]
        constraints = [
            models.UniqueConstraint(fields=["event", "name"], name="unique_ticket_name_per_event"),
        ]

    @property
    def available(self):
        return max(self.quantity - self.reserved, 0)

    def __str__(self):
        return f"{self.event} — {self.name}"
