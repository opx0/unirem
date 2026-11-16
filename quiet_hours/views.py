from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import QuietHoursForm
from .models import QuietHoursPreference


@login_required
@require_http_methods(["GET", "POST"])
def settings(request):
    preference = QuietHoursPreference.objects.filter(owner=request.user).first()
    if preference is None:
        preference = QuietHoursPreference(owner=request.user)
    form = QuietHoursForm(
        request.POST if request.method == "POST" else None, instance=preference
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Quiet hours preferences saved.")
        return redirect("quiet_hours:settings")
    return render(request, "quiet_hours/settings.html", {"form": form})
