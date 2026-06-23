from django.urls import path

from .views import SandboxVerifyView

urlpatterns = [
    path("verify/", SandboxVerifyView.as_view(), name="sandbox-verify"),
]
