from django.urls import path

from .views import (
    BuscarLugaresView,
    CalcularRutaView,
    EstimarTarifaView,
)


app_name = "tarifas"


urlpatterns = [
    path(
        "estimar/",
        EstimarTarifaView.as_view(),
        name="estimar-tarifa",
    ),
    path(
        "ruta/",
        CalcularRutaView.as_view(),
        name="calcular-ruta",
    ),
    path(
        "lugares/buscar/",
        BuscarLugaresView.as_view(),
        name="buscar-lugares",
    ),
]