from django.urls import path
from rest_framework.routers import (
    DefaultRouter,
)

from .views import (
    RegistrarVehiculoPropioView,
    TipoVehiculoViewSet,
)


app_name = "flota"

router = DefaultRouter()

router.register(
    "tipos-vehiculo",
    TipoVehiculoViewSet,
    basename="tipos-vehiculo",
)

urlpatterns = [
    path(
        "vehiculos/registro-propio/",
        RegistrarVehiculoPropioView.as_view(),
        name="registro-vehiculo-propio",
    ),
]

urlpatterns += router.urls