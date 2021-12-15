from __future__ import annotations

import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from django.conf import settings
from kuma.api.v1.decorators import require_subscriber
from kuma.api.v1.plus import api_list, ItemGenerationData
from kuma.notifications.models import Notification, Watch, NotificationData
from kuma.notifications.utils import process_changes


@never_cache
@require_http_methods(["GET"])
@require_subscriber
def notifications(request):
    # E.g. GET /api/v1/notifications/
    return _notification_list(request)


@api_list
def _notification_list(request) -> ItemGenerationData:
    filters = {}
    if 'filterStarred' in request.GET:
        filters['starred'] = any(i == request.GET.get('filterStarred') for i in ["true", "True"])
    type = request.GET.get('filterType', None)
    if type:
        filters['notification__type'] = type
    sort = request.GET.get('sort', None)
    order_by = '-notification__created'
    if sort and sort == 'title':
        order_by = 'notification__title'

    return (
        Notification.objects.filter(user_id=request.user.id, **filters)
        .select_related("notification")
        .order_by(order_by),
        lambda notification: notification.serialize(),
    )


@never_cache
@require_http_methods(["GET"])
@require_subscriber
def watched(request):
    # E.g. GET /api/v1/notifications/
    return _watched_list(request)


@api_list
def _watched_list(request) -> ItemGenerationData:
    return (
        Watch.objects.filter(users=request.user.id),
        lambda obj: obj.serialize(),
    )



@never_cache
@require_http_methods(["POST"])
@require_subscriber
def mark_as_read(request, id: int | str):
    # E.g.POST /api/v1/notifications/<id>/mark-as-read/
    kwargs = dict(user=request.user, read=False)

    if isinstance(id, int):
        kwargs["id"] = id

    unread = Notification.objects.filter(**kwargs)
    if isinstance(id, int) and not unread:
        return HttpResponseBadRequest("invalid 'id'")

    unread.update(read=True)
    return JsonResponse({"OK": True}, status=200)


@never_cache
@require_http_methods(["POST"])
@require_subscriber
def toggle_starred(request, id: int):
    # E.g.POST /api/v1/notifications/<id>/star/
    try:
        notification = Notification.objects.get(user=request.user, id=id)
    except Notification.DoesNotExist:
        return HttpResponseBadRequest("invalid 'id'")

    notification.starred = not notification.starred
    notification.save()
    return JsonResponse({"OK": True}, status=200)



@never_cache
@require_http_methods(["GET", "POST"])
@require_subscriber
def watch(request, url):
    # E.g.GET /api/v1/notifications/watch/en-US/docs/Web/CSS/
    if request.method == "GET":
        watched = Watch.objects.filter(users=request.user, url=url).first()
        status = "unwatched"
        if watched:
            status = "major"
        return JsonResponse({"ok": True, status: status}, status=200)

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("UTF-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "bad data"}, status=400)
        title = data.get("title", None)
        path = data.get("path", "")
        if not title:
            return JsonResponse({"ok": False, "error": "missing title"}, status=400)

        watched, _ = Watch.objects.get_or_create(url=url, title=title, path=path)
        watched.users.add(request.user)

        return JsonResponse({"ok": True}, status=200)

    return JsonResponse({"ok": False}, status=403)


@never_cache
@require_http_methods(["POST"])
def create(request):
    # E.g.GET /api/v1/notifications/create/
    auth = request.headers.get('Authorization')
    if not auth or auth != settings.NOTIFICATIONS_ADMIN_TOKEN:
        return JsonResponse({"ok": False, "error": "not authorized"}, status=401)

    try:
        data = json.loads(request.body.decode("UTF-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "bad data"}, status=400)

    page = data.get("page", "")
    if not page:
        return JsonResponse({"ok": False, "error": "missing page"}, status=400)

    title = data.get("title", "")
    text = data.get("text", "")

    if not title or not text:
        return JsonResponse({"ok": False, "error": "missing notification data"}, status=400)

    watchers = Watch.objects.filter(url=page)
    notification_data, _ = NotificationData.objects.get_or_create(text=title, title=title, type='content')
    for watcher in watchers:
        # considering the possibility of multiple pages existing for the same path
        for user in watcher.users.all():
            Notification.objects.create(notification=notification_data, user=user)

    return JsonResponse({"ok": True}, status=200)


@never_cache
@require_http_methods(["POST"])
def update(request):
    # E.g.GET /api/v1/notifications/update/
    auth = request.headers.get('Authorization')
    if not auth or auth != settings.NOTIFICATIONS_ADMIN_TOKEN:
        return JsonResponse({"ok": False, "error": "not authorized"}, status=401)

    # ToDo: Fetch file from S3
    changes = json.loads('{}')
    process_changes(changes)

    return JsonResponse({"ok": True}, status=200)
