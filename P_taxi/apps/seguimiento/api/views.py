"""Vistas de seguimiento."""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import (
    SimpleRateThrottle,
)
from rest_framework.views import APIView

from apps.pasajeros.models import Pasajero
from apps.viajes.models import Viaje


from ..models import (
    EstadoConductorTiempoReal,
)
from ..services import (
    actualizar_ubicacion,
    cambiar_disponibilidad,
    desconectar_conductor,
)
from .serializers import (
    DisponibilidadConductorSerializer,
    UbicacionConductorSerializer,
)


class ActualizarUbicacionThrottle(
    SimpleRateThrottle
):
    scope = "actualizar_ubicacion"

    def get_rate(self):
        return "60/minute"

    def get_cache_key(
        self,
        request,
        view,
    ):
        if not request.user.is_authenticated:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.pk),
        }


class DisponibilidadConductorView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = (
            DisponibilidadConductorSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            estado = cambiar_disponibilidad(
                usuario=request.user,
                disponible=(
                    serializer.validated_data[
                        "disponible"
                    ]
                ),
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "conductor_id": (
                    estado.conductor_id
                ),
                "en_linea": estado.en_linea,
                "disponible": estado.disponible,
                "viaje_actual_id": (
                    estado.viaje_actual_id
                ),
                "ultima_conexion": (
                    estado.ultima_conexion
                ),
            },
            status=status.HTTP_200_OK,
        )


class ActualizarUbicacionConductorView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    throttle_classes = [
        ActualizarUbicacionThrottle,
    ]

    def post(self, request):
        serializer = (
            UbicacionConductorSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            estado = actualizar_ubicacion(
                usuario=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "Ubicación actualizada."
                ),
                "conductor_id": (
                    estado.conductor_id
                ),
                "en_linea": estado.en_linea,
                "disponible": estado.disponible,
                "viaje_actual_id": (
                    estado.viaje_actual_id
                ),
                "ubicacion": {
                    "latitud": estado.latitud,
                    "longitud": estado.longitud,
                    "precision_metros": (
                        estado.precision_metros
                    ),
                    "velocidad_kmh": (
                        estado.velocidad_kmh
                    ),
                    "rumbo_grados": (
                        estado.rumbo_grados
                    ),
                    "fecha": (
                        estado.ultima_ubicacion
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )


class UbicacionConductorViajeView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        viaje_id,
    ):
        pasajero = (
            Pasajero.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not pasajero:
            raise ValidationError(
                "La cuenta no tiene perfil "
                "de pasajero."
            )

        try:
            viaje = (
                Viaje.objects
                .select_related("conductor")
                .get(
                    pk=viaje_id,
                    pasajero=pasajero,
                )
            )
        except Viaje.DoesNotExist:
            raise ValidationError(
                "El viaje no existe o no "
                "pertenece al pasajero."
            )

        if viaje.estado not in [
            "aceptado",
            "conductor_en_camino",
            "conductor_llego",
            "en_curso",
        ]:
            raise ValidationError(
                "La ubicación del conductor "
                "no está disponible en este estado."
            )

        if not viaje.conductor_id:
            raise ValidationError(
                "El viaje todavía no tiene "
                "conductor."
            )

        estado = (
            EstadoConductorTiempoReal.objects
            .filter(
                conductor_id=(
                    viaje.conductor_id
                )
            )
            .first()
        )

        if (
            not estado
            or not estado.tiene_ubicacion
            or not estado.ultima_ubicacion
        ):
            return Response(
                {
                    "ubicacion_disponible": False,
                    "ubicacion": None,
                },
                status=status.HTTP_200_OK,
            )

        segundos_transcurridos = (
            timezone.now()
            - estado.ultima_ubicacion
        ).total_seconds()

        return Response(
            {
                "ubicacion_disponible": True,
                "ubicacion_reciente": (
                    segundos_transcurridos <= 60
                ),
                "segundos_desde_actualizacion": (
                    int(segundos_transcurridos)
                ),
                "conductor_id": (
                    viaje.conductor_id
                ),
                "ubicacion": {
                    "latitud": estado.latitud,
                    "longitud": estado.longitud,
                    "precision_metros": (
                        estado.precision_metros
                    ),
                    "velocidad_kmh": (
                        estado.velocidad_kmh
                    ),
                    "rumbo_grados": (
                        estado.rumbo_grados
                    ),
                    "fecha": (
                        estado.ultima_ubicacion
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

class DesconectarConductorView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        try:
            estado = desconectar_conductor(
                usuario=request.user
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "Conductor desconectado "
                    "correctamente."
                ),
                "conductor_id": (
                    estado.conductor_id
                ),
                "en_linea": estado.en_linea,
                "disponible": estado.disponible,
                "viaje_actual_id": (
                    estado.viaje_actual_id
                ),
            },
            status=status.HTTP_200_OK,
        )