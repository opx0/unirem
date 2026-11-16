from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    return JsonResponse(
        {
            "name": "Campus Radar",
            "short_name": "Campus Radar",
            "start_url": reverse("home"),
            "scope": reverse("home"),
            "display": "standalone",
            "background_color": "#f5f7f5",
            "theme_color": "#153f42",
            "icons": [
                {
                    "src": static(f"core/icon-{size}.png"),
                    "sizes": f"{size}x{size}",
                    "type": "image/png",
                }
                for size in (192, 512)
            ],
        },
        content_type="application/manifest+json",
    )


@require_GET
@never_cache
def service_worker(request):
    return render(
        request, "core/service-worker.js", content_type="application/javascript"
    )
