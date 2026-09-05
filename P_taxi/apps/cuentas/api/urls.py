from django.urls import path

from .password_views import (
    RestablecerPasswordView,
    SolicitarCodigoPasswordView,
)
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
    path(
        "password/solicitar/",
        SolicitarCodigoPasswordView.as_view(),
        name="solicitar-codigo-password",
    ),
    path(
        "password/restablecer/",
        RestablecerPasswordView.as_view(),
        name="restablecer-password",
    ),
]