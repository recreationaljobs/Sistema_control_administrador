"""Vista para consultar el detalle de un viaje."""

from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from App_taxi.models import Conductor
from apps.pasajeros.models import Pasajero
from apps.viajes.models import Viaje

from .serializers import ViajeSerializer


class DetalleViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request, viaje_id):
        usuario = request.user

        try:
            viaje = (
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
                .get(id=viaje_id)
            )
        except Viaje.DoesNotExist:
            raise NotFound(
                "El viaje solicitado no existe."
            )

        rol_codigo = (
            usuario.rol.codigo
            if usuario.rol
            else ""
        )

        tiene_permiso = False

        if rol_codigo == "pasajero":
            pasajero = (
                Pasajero.objects
                .filter(usuario=usuario)
                .first()
            )

            tiene_permiso = (
                pasajero is not None
                and viaje.pasajero_id
                == pasajero.id
            )

        elif rol_codigo == "taxista":
            conductor = (
                Conductor.objects
                .filter(usuario=usuario)
                .first()
            )

            tiene_permiso = (
                conductor is not None
                and viaje.conductor_id
                == conductor.id
            )

        if not tiene_permiso:
            raise PermissionDenied(
                "No tienes permiso para consultar "
                "este viaje."
            )

        serializer = ViajeSerializer(
            viaje,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data
        )