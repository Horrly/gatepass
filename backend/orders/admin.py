from django.contrib import admin

from .models import Order, OrderItem, Ticket


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "event", "buyer", "status", "total", "created_at"]
    list_filter = ["status"]
    search_fields = ["reference", "email"]
    inlines = [OrderItemInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["code", "ticket_type", "order", "checked_in_at"]
