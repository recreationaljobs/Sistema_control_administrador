"""Vistas para consultar el historial de viajes."""

from rest_framework.exceptions import (
    PermissionDenied,
)
from rest_framework.generics import ListAPIView
from rest_framework.permissions import (
    IsAuthenticated,
)

from App_taxi.models import Conductor
from apps.pasajeros.models import Pasajero
from apps.viajes.models import Viaje

from .serializers import ViajeSerializer


ESTADOS_HISTORICOS = [
    "completado",
    "cancelado",
]


class HistorialViajesView(ListAPIView):
    permission_classes = [
        IsAuthenticated,
    ]

    serializer_class = ViajeSerializer

    def get_queryset(self):
        usuario = self.request.user

        queryset = (
            Viaje.objects
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "conductor",
                "conductor__usuario",
                "vehiculo",
                "tipo_vehiculo",
                "sucursal",
            )
            .filter(
                estado__in=ESTADOS_HISTORICOS
            )
            .order_by(
                "-fecha_solicitud"
            )
        )

        rol_codigo = (
            usuario.rol.codigo
            if usuario.rol
            else ""
        )

        if rol_codigo == "pasajero":
            pasajero = (
                Pasajero.objects
                .filter(usuario=usuario)
                .first()
            )

            if not pasajero:
                return queryset.none()

            return queryset.filter(
                pasajero=pasajero
            )

        if rol_codigo == "taxista":
            conductor = (
                Conductor.objects
                .filter(usuario=usuario)
                .first()
            )

            if not conductor:
                return queryset.none()

            return queryset.filter(
                conductor=conductor
            )

        raise PermissionDenied(
            "Esta cuenta no puede consultar "
            "el historial móvil de viajes."
        )