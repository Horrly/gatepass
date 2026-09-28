from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Event

pytestmark = pytest.mark.django_db


def future(days=5):
    return (timezone.now() + timedelta(days=days)).isoformat()


class TestPublicListing:
    def test_lists_only_published_upcoming_events(self, anon, organizer, event, regular):
        Event.objects.create(organizer=organizer, title="Draft", venue="x", city="Lagos",
                             starts_at=timezone.now() + timedelta(days=3))
        Event.objects.create(organizer=organizer, title="Past", venue="x", city="Lagos",
                             starts_at=timezone.now() - timedelta(days=3), is_published=True)

        res = anon.get("/api/events/")
        assert res.status_code == 200
        assert [e["title"] for e in res.data] == ["Lagos Tech Meetup"]
        assert res.data[0]["min_price"] == 500_000
        assert res.data[0]["is_sold_out"] is False

    def test_search_and_city_filter(self, anon, organizer, event):
        Event.objects.create(organizer=organizer, title="Ife Hackathon", venue="OAU", city="Ile-Ife",
                             starts_at=timezone.now() + timedelta(days=3), is_published=True)
        assert [e["title"] for e in anon.get("/api/events/?q=hack").data] == ["Ife Hackathon"]
        assert [e["title"] for e in anon.get("/api/events/?city=lagos").data] == ["Lagos Tech Meetup"]

    def test_public_detail_hides_inventory_internals(self, anon, event, regular):
        ticket = anon.get(f"/api/events/{event.slug}/").data["ticket_types"][0]
        assert ticket["available"] == 5
        assert "reserved" not in ticket

    def test_drafts_visible_only_to_organizer(self, anon, org_api, other_api, event):
        event.is_published = False
        event.save()
        assert anon.get(f"/api/events/{event.slug}/").status_code == 404
        assert other_api.get(f"/api/events/{event.slug}/").status_code == 404
        res = org_api.get(f"/api/events/{event.slug}/")
        assert res.status_code == 200 and res.data["is_organizer"] is True


class TestOrganizerManagement:
    def test_create_event_starts_as_draft(self, org_api):
        res = org_api.post("/api/events/", {
            "title": "Design Night", "venue": "Yaba", "city": "Lagos",
            "starts_at": future(), "is_published": False,
        }, format="json")
        assert res.status_code == 201
        assert res.data["slug"] == "design-night"
        assert res.data["is_published"] is False

    def test_duplicate_titles_get_unique_slugs(self, org_api, event):
        res = org_api.post("/api/events/", {"title": event.title, "venue": "x", "city": "y",
                                            "starts_at": future()}, format="json")
        assert res.data["slug"].startswith("lagos-tech-meetup-")

    def test_rejects_past_start_and_bad_end(self, org_api):
        past = org_api.post("/api/events/", {"title": "Old", "venue": "x", "city": "y",
                                             "starts_at": future(-1)}, format="json")
        assert "starts_at" in past.data
        bad_end = org_api.post("/api/events/", {"title": "New", "venue": "x", "city": "y",
                                                "starts_at": future(5), "ends_at": future(4)}, format="json")
        assert "ends_at" in bad_end.data

    def test_cannot_publish_without_ticket_types(self, org_api, event):
        event.is_published = False
        event.save()
        res = org_api.patch(f"/api/events/{event.slug}/", {"is_published": True}, format="json")
        assert res.status_code == 400

    def test_publish_with_ticket_types(self, org_api, event, regular):
        event.is_published = False
        event.save()
        res = org_api.patch(f"/api/events/{event.slug}/", {"is_published": True}, format="json")
        assert res.status_code == 200 and res.data["is_published"] is True

    def test_only_organizer_can_edit(self, other_api, anon, event):
        assert other_api.patch(f"/api/events/{event.slug}/", {"title": "Hacked"}, format="json").status_code == 403
        assert anon.patch(f"/api/events/{event.slug}/", {"title": "Hacked"}, format="json").status_code == 401

    def test_mine_lists_drafts_too(self, org_api, other_api, organizer, event):
        Event.objects.create(organizer=organizer, title="Draft", venue="x", city="y",
                             starts_at=timezone.now() + timedelta(days=30))
        assert len(org_api.get("/api/events/mine/").data) == 2
        assert other_api.get("/api/events/mine/").data == []

    def test_delete_blocked_once_orders_exist(self, org_api, event, regular, buy):
        buy(event, (regular, 1))
        assert org_api.delete(f"/api/events/{event.slug}/").status_code == 403


class TestTicketTypes:
    def test_add_ticket_type(self, org_api, event):
        res = org_api.post(f"/api/events/{event.slug}/ticket-types/",
                           {"name": "Early bird", "price": 250_000, "quantity": 50}, format="json")
        assert res.status_code == 201
        assert res.data["available"] == 50 and res.data["reserved"] == 0

    @pytest.mark.parametrize("price, ok", [(0, True), (5_000, False), (10_000, True)])
    def test_minimum_paid_price(self, org_api, event, price, ok):
        res = org_api.post(f"/api/events/{event.slug}/ticket-types/",
                           {"name": f"T{price}", "price": price, "quantity": 5}, format="json")
        assert (res.status_code == 201) is ok

    def test_duplicate_name_rejected(self, org_api, event, regular):
        res = org_api.post(f"/api/events/{event.slug}/ticket-types/",
                           {"name": "regular", "price": 0, "quantity": 5}, format="json")
        assert res.status_code == 400

    def test_other_users_cannot_add(self, other_api, event):
        res = other_api.post(f"/api/events/{event.slug}/ticket-types/",
                             {"name": "Fake", "price": 0, "quantity": 5}, format="json")
        assert res.status_code == 403

    def test_cannot_shrink_below_sold_or_reprice_after_sales(self, org_api, event, regular, buy):
        buy(event, (regular, 3))
        shrink = org_api.patch(f"/api/ticket-types/{regular.id}/", {"quantity": 2}, format="json")
        assert shrink.status_code == 400
        reprice = org_api.patch(f"/api/ticket-types/{regular.id}/", {"price": 900_000}, format="json")
        assert reprice.status_code == 400
        grow = org_api.patch(f"/api/ticket-types/{regular.id}/", {"quantity": 10}, format="json")
        assert grow.status_code == 200 and grow.data["available"] == 7

    def test_delete_only_without_orders(self, org_api, event, regular, vip, buy):
        buy(event, (regular, 1))
        assert org_api.delete(f"/api/ticket-types/{regular.id}/").status_code == 403
        assert org_api.delete(f"/api/ticket-types/{vip.id}/").status_code == 204

    def test_other_users_cannot_edit(self, other_api, regular):
        assert other_api.patch(f"/api/ticket-types/{regular.id}/", {"quantity": 1}, format="json").status_code == 404
