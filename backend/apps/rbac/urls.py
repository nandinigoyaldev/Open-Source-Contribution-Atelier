from django.urls import path

from . import views

app_name = "rbac"

urlpatterns = [
    path("roles/", views.RoleListView.as_view(), name="list_roles"),
    path("permissions/", views.PermissionListView.as_view(), name="list_permissions"),
    path("assign/", views.AssignRoleView.as_view(), name="assign_role"),
    path("revoke/", views.RevokeRoleView.as_view(), name="revoke_role"),
    path("audit-logs/", views.AuditLogListView.as_view(), name="list_audit_logs"),
]
