from django.db.models import Q
from django.views.generic import ListView

from accounts.permissions import RoleRequiredMixin
from .models import ActivityLog


class ActivityLogView(RoleRequiredMixin, ListView):
    """Oversight view — Admin, Manager and Auditor may review activity."""

    allowed_roles = ("admin", "manager", "auditor")
    model = ActivityLog
    template_name = "audit/activity_list.html"
    context_object_name = "logs"
    paginate_by = 30

    def get_queryset(self):
        qs = ActivityLog.objects.select_related("user")
        action = self.request.GET.get("action")
        q = self.request.GET.get("q")
        if action:
            qs = qs.filter(action=action)
        if q:
            qs = qs.filter(
                Q(object_repr__icontains=q)
                | Q(model_name__icontains=q)
                | Q(user__username__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.dict()
        return ctx
