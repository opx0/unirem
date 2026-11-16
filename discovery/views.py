from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from core.models import Event, Notice, Opportunity, Task


@login_required
def search(request):
    query = request.GET.get("q", "").strip()[:200]
    record_type = request.GET.get("type", "")
    types = ("notices", "events", "tasks", "opportunities")
    if record_type not in types:
        record_type = ""

    results = []
    if query:
        querysets = {
            "notices": Notice.objects.filter(owner=request.user)
            .filter(
                Q(title__icontains=query)
                | Q(original_text__icontains=query)
                | Q(summary__icontains=query)
                | Q(
                    extraction_runs__owner=request.user,
                    extraction_runs__extracted_text__icontains=query,
                )
                | Q(
                    extraction_runs__owner=request.user,
                    extraction_runs__reviewed_text__icontains=query,
                )
            )
            .distinct(),
            "events": Event.objects.filter(owner=request.user).filter(
                Q(title__icontains=query) | Q(location__icontains=query)
            ),
            "tasks": Task.objects.filter(owner=request.user).filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            ),
            "opportunities": Opportunity.objects.filter(owner=request.user).filter(
                Q(title__icontains=query) | Q(notes__icontains=query)
            ),
        }
        for kind in types:
            if record_type and kind != record_type:
                continue
            queryset = querysets[kind].order_by("pk")
            if kind != "notices":
                queryset = queryset.select_related("notice")
            for item in queryset:
                source = None
                if (
                    kind != "notices"
                    and item.notice_id
                    and item.notice.owner_id == request.user.pk
                ):
                    source = item.notice
                results.append({"kind": kind, "item": item, "source": source})

    page = Paginator(results, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "discovery/search.html",
        {"query": query, "record_type": record_type, "types": types, "page": page},
    )
