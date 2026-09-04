"""Vistas de viajes."""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
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
import math

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from apps.tarifas.services import (
    calcular_distancia_haversine,
)
from django.db.models import (
    Avg,
    Count,
    Q,
)

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
)
from apps.pasajeros.models import Pasajero
from apps.seguimiento.services import (
    validar_conductor_disponible,
)

from ..models import Viaje
from ..services import (
    ESTADOS_VIAJE_ACTIVO,
    aceptar_viaje,
    cambiar_estado_viaje_conductor,
    cancelar_viaje_pasajero,
    liberar_viaje_por_conductor,
)
from .serializers import (
    CambiarEstadoViajeSerializer,
    CancelarViajeSerializer,
    SolicitarViajeSerializer,
    ViajeDisponibleSerializer,
    ViajeSerializer,
)


def obtener_viaje_detallado(
    viaje_id,
):
    return (
        Viaje.objects
        .select_related(
            "pasajero",
            "pasajero__usuario",
            "conductor",
            "vehiculo",
            "tipo_vehiculo",
            "sucursal",
        )
        .get(pk=viaje_id)
    )


class SolicitarViajeThrottle(
    SimpleRateThrottle
):
    scope = "solicitar_viaje"

    def get_rate(self):
        return "10/minute"

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


class SolicitarViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    throttle_classes = [
        SolicitarViajeThrottle,
    ]

    def post(self, request):
        serializer = SolicitarViajeSerializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        viaje = serializer.save()

        viaje = obtener_viaje_detallado(
            viaje.id
        )

        return Response(
            {
                "mensaje": (
                    "La solicitud de viaje fue "
                    "creada correctamente."
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ViajesDisponiblesConductorView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        conductor = (
            Conductor.objects
            .select_related("usuario")
            .filter(
                usuario=request.user,
                estado_verificacion="aprobado",
                activo=True,
            )
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta no tiene un conductor "
                "aprobado y activo."
            )

        try:
            estado_tiempo_real = (
                validar_conductor_disponible(
                    conductor=conductor
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )
        
        if not estado_tiempo_real.tiene_ubicacion:
            raise ValidationError(
                "Debes enviar tu ubicación antes "
                "de consultar viajes cercanos."
            )

        asignacion = (
            AsignacionVehiculo.objects
            .select_related(
                "vehiculo",
                "vehiculo__tipo_vehiculo",
            )
            .filter(
                conductor=conductor,
                activa=True,
                vehiculo__estado_verificacion=(
                    "aprobado"
                ),
            )
            .first()
        )

        if not asignacion:
            raise ValidationError(
                "No tienes un vehículo "
                "activo asignado."
            )

        tipo_vehiculo_id = (
            asignacion.vehiculo
            .tipo_vehiculo_id
        )

        if not tipo_vehiculo_id:
            raise ValidationError(
                "El vehículo no tiene un "
                "tipo configurado."
            )

        ruta_tipo_calificacion = (
            "pasajero__usuario__"
            "calificaciones_recibidas__tipo"
        )

        filtro_calificacion = Q(
            **{
                ruta_tipo_calificacion: (
                    "conductor_a_pasajero"
                )
            }
        )

        ruta_puntuacion = (
            "pasajero__usuario__"
            "calificaciones_recibidas__"
            "puntuacion"
        )

        ruta_calificaciones = (
            "pasajero__usuario__"
            "calificaciones_recibidas"
        )

        radio_maximo_km = Decimal("20")

        latitud_conductor = (
            estado_tiempo_real.latitud
        )

        longitud_conductor = (
            estado_tiempo_real.longitud
        )

        delta_latitud = (
            radio_maximo_km
            / Decimal("111")
        )

        coseno_latitud = Decimal(
            str(
                math.cos(
                    math.radians(
                        float(latitud_conductor)
                    )
                )
            )
        )

        delta_longitud = (
            radio_maximo_km
            / (
                Decimal("111")
                * coseno_latitud
            )
        )

        ruta_tipo_calificacion = (
            "pasajero__usuario__"
            "calificaciones_recibidas__tipo"
        )

        filtro_calificacion = Q(
            **{
                ruta_tipo_calificacion: (
                    "conductor_a_pasajero"
                )
            }
        )

        ruta_puntuacion = (
            "pasajero__usuario__"
            "calificaciones_recibidas__"
            "puntuacion"
        )

        ruta_calificaciones = (
            "pasajero__usuario__"
            "calificaciones_recibidas"
        )

        candidatos = list(
            Viaje.objects
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "tipo_vehiculo",
            )
            .annotate(
                pasajero_calificacion_promedio=(
                    Avg(
                        ruta_puntuacion,
                        filter=filtro_calificacion,
                    )
                ),
                pasajero_total_calificaciones=(
                    Count(
                        ruta_calificaciones,
                        filter=filtro_calificacion,
                        distinct=True,
                    )
                ),
            )
            .filter(
                estado="buscando_conductor",
                tipo_vehiculo_id=(
                    tipo_vehiculo_id
                ),
                origen_latitud__range=(
                    latitud_conductor
                    - delta_latitud,
                    latitud_conductor
                    + delta_latitud,
                ),
                origen_longitud__range=(
                    longitud_conductor
                    - delta_longitud,
                    longitud_conductor
                    + delta_longitud,
                ),
            )
            .order_by(
                "fecha_solicitud"
            )[:200]
        )

        for viaje in candidatos:
            distancia = (
                calcular_distancia_haversine(
                    origen_latitud=(
                        latitud_conductor
                    ),
                    origen_longitud=(
                        longitud_conductor
                    ),
                    destino_latitud=(
                        viaje.origen_latitud
                    ),
                    destino_longitud=(
                        viaje.origen_longitud
                    ),
                )
            )

            viaje.distancia_recogida_km = (
                distancia.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            )

        viajes = []
        radio_utilizado = Decimal("20")

        for radio in [
            Decimal("5"),
            Decimal("10"),
            Decimal("20"),
        ]:
            viajes = [
                viaje
                for viaje in candidatos
                if (
                    viaje.distancia_recogida_km
                    <= radio
                )
            ]

            if viajes:
                radio_utilizado = radio
                break

        viajes.sort(
            key=lambda viaje: (
                viaje.distancia_recogida_km,
                viaje.fecha_solicitud,
            )
        )

        viajes = viajes[:50]
        return Response(
            {
                "tipo_vehiculo_id": (
                    tipo_vehiculo_id
                ),
                 "radio_busqueda_km": (
                    radio_utilizado
                ),
                "cantidad": len(viajes),
                "viajes": (
                    ViajeDisponibleSerializer(
                        viajes,
                        many=True,
                        context={
                            "request": request,
                            "conductor": conductor,
                        },
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )


class AceptarViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        conductor = (
            Conductor.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta autenticada no tiene "
                "un perfil de conductor."
            )

        try:
            viaje = aceptar_viaje(
                viaje_id=viaje_id,
                conductor=conductor,
                usuario=request.user,
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        viaje = obtener_viaje_detallado(
            viaje.id
        )

        return Response(
            {
                "mensaje": (
                    "El viaje fue aceptado "
                    "correctamente."
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class CambiarEstadoViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        serializer = (
            CambiarEstadoViajeSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        conductor = (
            Conductor.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta no tiene un "
                "perfil de conductor."
            )

        try:
            viaje = (
                cambiar_estado_viaje_conductor(
                    viaje_id=viaje_id,
                    conductor=conductor,
                    estado_nuevo=(
                        serializer
                        .validated_data["estado"]
                    ),
                    usuario=request.user,
                    latitud=(
                        serializer
                        .validated_data
                        .get("latitud")
                    ),
                    longitud=(
                        serializer
                        .validated_data
                        .get("longitud")
                    ),
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        viaje = obtener_viaje_detallado(
            viaje.id
        )

        return Response(
            {
                "mensaje": (
                    "Estado del viaje actualizado "
                    "correctamente."
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class MiViajeActivoView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        pasajero = (
            Pasajero.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        conductor = (
            Conductor.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if pasajero:
            filtros_propietario = {
                "pasajero": pasajero,
            }

            tipo_cuenta = "pasajero"

        elif conductor:
            filtros_propietario = {
                "conductor": conductor,
            }

            tipo_cuenta = "conductor"

        else:
            return Response(
                {
                    "detail": (
                        "La cuenta no tiene perfil "
                        "de pasajero ni conductor."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        viaje = (
            Viaje.objects
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "conductor",
                "vehiculo",
                "tipo_vehiculo",
                "sucursal",
            )
            .filter(
                estado__in=(
                    ESTADOS_VIAJE_ACTIVO
                ),
                **filtros_propietario,
            )
            .order_by(
                "-fecha_solicitud"
            )
            .first()
        )

        return Response(
            {
                "tipo_cuenta": tipo_cuenta,
                "tiene_viaje_activo": (
                    viaje is not None
                ),
                "viaje": (
                    ViajeSerializer(viaje).data
                    if viaje
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class CancelarViajePasajeroView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        serializer = CancelarViajeSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        pasajero = (
            Pasajero.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not pasajero:
            raise ValidationError(
                "La cuenta no tiene un "
                "perfil de pasajero."
            )

        try:
            viaje = cancelar_viaje_pasajero(
                viaje_id=viaje_id,
                pasajero=pasajero,
                usuario=request.user,
                motivo=(
                    serializer
                    .validated_data["motivo"]
                ),
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        viaje = obtener_viaje_detallado(
            viaje.id
        )

        return Response(
            {
                "mensaje": (
                    "El viaje fue cancelado "
                    "correctamente."
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class LiberarViajeConductorView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        serializer = CancelarViajeSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        conductor = (
            Conductor.objects
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta no tiene un "
                "perfil de conductor."
            )

        try:
            viaje = (
                liberar_viaje_por_conductor(
                    viaje_id=viaje_id,
                    conductor=conductor,
                    usuario=request.user,
                    motivo=(
                        serializer
                        .validated_data["motivo"]
                    ),
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        viaje = obtener_viaje_detallado(
            viaje.id
        )

        return Response(
            {
                "mensaje": (
                    "El viaje fue liberado. "
                    "Otro conductor podrá aceptarlo."
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_200_OK,
        )
