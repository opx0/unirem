from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import SourceConnection


@login_required
def settings(request):
    manual_connected = SourceConnection.objects.filter(
        owner=request.user, source=SourceConnection.Source.MANUAL
    ).exists()
    return render(
        request, "connections/settings.html", {"manual_connected": manual_connected}
    )


@login_required
@require_POST
def connect_manual(request):
    SourceConnection.objects.get_or_create(
        owner=request.user, source=SourceConnection.Source.MANUAL
    )
    messages.success(
        request, "Manual source enabled. Add notices yourself using Capture."
    )
    return redirect("connections:settings")


@login_required
@require_POST
def disconnect_manual(request):
    SourceConnection.objects.filter(
        owner=request.user, source=SourceConnection.Source.MANUAL
    ).delete()
    messages.success(
        request, "Manual source disconnected. Existing notices were not deleted."
    )
    return redirect("connections:settings")
