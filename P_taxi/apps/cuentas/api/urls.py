from django.urls import path

from .views import (
    ActivarConductorView,
    RegistroConductorView,
)

app_name = "cuentas_api"

urlpatterns = [
    path(
        "conductores/activar/",
        ActivarConductorView.as_view(),
        name="activar-conductor",
    ),
    path(
        "conductores/registro/",
        RegistroConductorView.as_view(),
        name="registro-conductor",
    ),
]