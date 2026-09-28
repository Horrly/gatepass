from django.contrib import admin

from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "organizer", "city", "starts_at", "is_published"]
    list_filter = ["is_published", "city"]
    search_fields = ["title", "venue"]
    inlines = [TicketTypeInline]
