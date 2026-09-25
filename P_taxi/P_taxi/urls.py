"""
URL configuration for P_taxi project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    # API administrativa
    path("api/", include("App_taxi.api.urls")),

    # API móvil Zenda
    path(
        "api/v1/",
        include("apps.urls"),
    ),
]


# Solo para desarrollo local.
# En producción las imágenes las servirá Nginx.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )