from django.urls import path

from .views import (
    MiPerfilPasajeroView,
    RegistroPasajeroView,
)


app_name = "pasajeros"

urlpatterns = [
    path(
        "registro/",
        RegistroPasajeroView.as_view(),
        name="registro-pasajero",
    ),
    path(
        "mi-perfil/",
        MiPerfilPasajeroView.as_view(),
        name="mi-perfil-pasajero",
    ),
]