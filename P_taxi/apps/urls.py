from django.urls import include, path # pyright: ignore[reportMissingModuleSource]

from .common.views import (
    EstadoAPIView,
    VersionAppAPIView,
)


urlpatterns = [
    path(
        "",
        EstadoAPIView.as_view(),
        name="estado-api-v1",
    ),

    path(
        "cuentas/",
        include(
            "apps.cuentas.api.urls"
        ),
    ),

    path(
        "pasajeros/",
        include(
            "apps.pasajeros.api.urls"
        ),
    ),

    path(
        "flota/",
        include(
            "apps.flota.api.urls"
        ),
    ),

    path(
        "viajes/",
        include(
            "apps.viajes.api.urls"
        ),
    ),

    path(
        "tarifas/",
        include(
            "apps.tarifas.api.urls"
        ),
    ),

    path(
        "seguimiento/",
        include(
            "apps.seguimiento.api.urls"
        ),
    ),
        path(
        "version-app/",
        VersionAppAPIView.as_view(),
        name="version-app",
    ),
]