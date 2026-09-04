from django.urls import path

from .conductores_cercanos_views import (
    ConductoresCercanosView,
)
from .views import (
    ActualizarUbicacionConductorView,
    DesconectarConductorView,
    DisponibilidadConductorView,
    UbicacionConductorViajeView,
)


app_name = "seguimiento"


urlpatterns = [
    path(
        "disponibilidad/",
        DisponibilidadConductorView.as_view(),
        name="disponibilidad-conductor",
    ),
    path(
        "ubicacion/",
        ActualizarUbicacionConductorView.as_view(),
        name="actualizar-ubicacion",
    ),
    path(
        "conductores-cercanos/",
        ConductoresCercanosView.as_view(),
        name="conductores-cercanos",
    ),
    path(
        "viajes/<uuid:viaje_id>/"
        "ubicacion-conductor/",
        UbicacionConductorViajeView.as_view(),
        name="ubicacion-conductor-viaje",
    ),
    path(
        "desconectar/",
        DesconectarConductorView.as_view(),
        name="desconectar-conductor",
    ),
]
