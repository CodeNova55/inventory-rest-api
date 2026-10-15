from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("inventory.urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("", RedirectView.as_view(url="/api/")),
]
