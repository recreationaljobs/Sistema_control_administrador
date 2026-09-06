"""Consulta móvil de conductores disponibles cerca del pasajero."""

from datetime import timedelta
from math import (
    asin,
    cos,
    radians,
    sin,
    sqrt,
)

from django.utils import timezone # pyright: ignore[reportMissingModuleSource]
from rest_framework import serializers, status # type: ignore
from rest_framework.exceptions import ValidationError # type: ignore
from rest_framework.permissions import IsAuthenticated # pyright: ignore[reportMissingImports]
from rest_framework.response import Response # type: ignore
from rest_framework.views import APIView # pyright: ignore[reportMissingImports]

from App_taxi.models import AsignacionVehiculo
from apps.pasajeros.models import Pasajero

from ..models import EstadoConductorTiempoReal


RADIO_MAXIMO_KM = 30
SEGUNDOS_UBICACION_RECIENTE = 60


class ConsultarConductoresCercanosSerializer(
    serializers.Serializer
):
    tipo_vehiculo_id = serializers.IntegerField(
        min_value=1,
    )
    latitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-90,
        max_value=90,
    )
    longitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-180,
        max_value=180,
    )
    radio_km = serializers.DecimalField(
        max_digits=30,
        decimal_places=2,
        min_value=1,
        max_value=RADIO_MAXIMO_KM,
        required=False,
        default=RADIO_MAXIMO_KM,
    )


class ConductoresCercanosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pasajero = (
            Pasajero.objects
            .filter(usuario=request.user)
            .first()
        )

        if not pasajero:
            raise ValidationError(
                "La cuenta no tiene perfil de pasajero."
            )

        entrada = ConsultarConductoresCercanosSerializer(
            data=request.query_params
        )
        entrada.is_valid(raise_exception=True)

        datos = entrada.validated_data
        latitud = float(datos["latitud"])
        longitud = float(datos["longitud"])
        radio_km = float(datos["radio_km"])
        tipo_vehiculo_id = datos["tipo_vehiculo_id"]

        ubicacion_minima = (
            timezone.now()
            - timedelta(
                seconds=SEGUNDOS_UBICACION_RECIENTE
            )
        )

        estados = list(
            EstadoConductorTiempoReal.objects
            .select_related("conductor")
            .filter(
                en_linea=True,
                disponible=True,
                viaje_actual__isnull=True,
                ultima_ubicacion__gte=ubicacion_minima,
                conductor__activo=True,
                conductor__estado_verificacion="aprobado",
            )
            .exclude(
                latitud__isnull=True,
            )
            .exclude(
                longitud__isnull=True,
            )[:200]
        )

        conductor_ids = [
            estado.conductor_id
            for estado in estados
        ]

        asignaciones = (
            AsignacionVehiculo.objects
            .select_related(
                "vehiculo",
                "vehiculo__tipo_vehiculo",
            )
            .filter(
                conductor_id__in=conductor_ids,
                activa=True,
                vehiculo__tipo_vehiculo_id=(
                    tipo_vehiculo_id
                ),
                vehiculo__estado_verificacion="aprobado",
            )
        )

        asignacion_por_conductor = {
            asignacion.conductor_id: asignacion
            for asignacion in asignaciones
        }

        conductores = []

        for estado in estados:
            asignacion = asignacion_por_conductor.get(
                estado.conductor_id
            )

            if not asignacion:
                continue

            distancia_km = self._distancia_haversine(
                latitud_origen=latitud,
                longitud_origen=longitud,
                latitud_destino=float(estado.latitud),
                longitud_destino=float(estado.longitud),
            )

            if distancia_km > radio_km:
                continue

            tipo = asignacion.vehiculo.tipo_vehiculo

            conductores.append(
                {
                    "conductor_id": estado.conductor_id,
                    "latitud": estado.latitud,
                    "longitud": estado.longitud,
                    "rumbo_grados": estado.rumbo_grados,
                    "distancia_km": round(distancia_km, 2),
                    "tipo_vehiculo": {
                        "id": tipo.id,
                        "codigo": tipo.codigo,
                        "nombre": tipo.nombre,
                    },
                }
            )

        conductores.sort(
            key=lambda elemento: elemento["distancia_km"]
        )

        return Response(
            {
                "cantidad": len(conductores),
                "radio_km": radio_km,
                "conductores": conductores[:50],
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _distancia_haversine(
        *,
        latitud_origen,
        longitud_origen,
        latitud_destino,
        longitud_destino,
    ):
        radio_tierra_km = 6371
        diferencia_latitud = radians(
            latitud_destino - latitud_origen
        )
        diferencia_longitud = radians(
            longitud_destino - longitud_origen
        )

        valor = (
            sin(diferencia_latitud / 2) ** 2
            + cos(radians(latitud_origen))
            * cos(radians(latitud_destino))
            * sin(diferencia_longitud / 2) ** 2
        )

        return radio_tierra_km * 2 * asin(sqrt(valor))
