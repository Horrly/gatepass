from rest_framework import permissions


class IsOrganizerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        event = getattr(obj, "event", obj)
        return event.organizer_id == request.user.id
