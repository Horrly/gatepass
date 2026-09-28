from django.conf import settings
from django.db import connection
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Used by Render's health check: confirms the app is up and the DB is reachable."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_GET
def spa(request):
    """Serve the built React app for any non-API path (e.g. /rooms/general).

    React Router then takes over in the browser. In development the Vite dev
    server serves the app instead, so this only matters once `npm run build`
    has produced frontend/dist.
    """
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return HttpResponse(
            "Frontend not built. Run the Vite dev server (npm run dev) or `npm run build`.",
            status=404,
            content_type="text/plain",
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    # index.html must never be cached, or users keep loading old JS bundles after a deploy.
    response["Cache-Control"] = "no-cache"
    return response
