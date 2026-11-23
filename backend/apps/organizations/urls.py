from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .sso_views import OrganizationSSOConfigView, OrganizationSSOLinkView
from .views import OrganizationMembershipViewSet, OrganizationViewSet

router = DefaultRouter()
router.register(r"", OrganizationViewSet, basename="organization")

membership_list = OrganizationMembershipViewSet.as_view(
    {"get": "list", "post": "create"}
)
membership_detail = OrganizationMembershipViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path(
        "<int:organization_pk>/members/",
        membership_list,
        name="organization-members-list",
    ),
    path(
        "<int:organization_pk>/members/<int:pk>/",
        membership_detail,
        name="organization-members-detail",
    ),
    path(
        "<int:organization_pk>/sso/",
        OrganizationSSOConfigView.as_view(),
        name="organization-sso-config",
    ),
    path(
        "<int:organization_pk>/sso/link/",
        OrganizationSSOLinkView.as_view(),
        name="organization-sso-link",
    ),
    path("", include(router.urls)),
]
