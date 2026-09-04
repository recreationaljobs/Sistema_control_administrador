"""Serializadores para ofertas de viajes."""

from math import (
    asin,
    ceil,
    cos,
    radians,
    sin,
    sqrt,
)

from django.db.models import (
    Avg,
    Count,
)
from rest_framework import serializers

from App_taxi.models import (
    AsignacionVehiculo,
)
from apps.seguimiento.models import (
    EstadoConductorTiempoReal,
)
from apps.viajes.models import (
    CalificacionViaje,
    OfertaViaje,
)


VELOCIDAD_PROMEDIO_RECOGIDA_KMH = 25


class CrearOfertaViajeSerializer(
    serializers.Serializer
):
    monto_propuesto = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=1,
    )

    mensaje = serializers.CharField(
        max_length=250,
        required=False,
        allow_blank=True,
        default="",
    )


class OfertaViajeSerializer(
    serializers.ModelSerializer
):
    viaje_id = serializers.UUIDField(
        read_only=True,
    )

    conductor = serializers.SerializerMethodField()
    tiempo_recogida_minutos = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = OfertaViaje

        fields = [
            "id",
            "viaje_id",
            "conductor",
            "tarifa_original",
            "monto_propuesto",
            "mensaje",
            "estado",
            "tiempo_recogida_minutos",
            "fecha_creacion",
            "fecha_vencimiento",
            "fecha_respuesta",
        ]

    def get_conductor(self, oferta):
        conductor = oferta.conductor

        resumen = (
            CalificacionViaje.objects
            .filter(
                usuario_evaluado_id=(
                    conductor.usuario_id
                ),
                tipo=(
                    CalificacionViaje
                    .PASAJERO_A_CONDUCTOR
                ),
            )
            .aggregate(
                promedio=Avg("puntuacion"),
                total=Count("id"),
            )
        )

        promedio = resumen["promedio"]

        asignacion = (
            AsignacionVehiculo.objects
            .select_related(
                "vehiculo",
                "vehiculo__tipo_vehiculo",
            )
            .filter(
                conductor=conductor,
                activa=True,
            )
            .first()
        )

        vehiculo_data = None

        if asignacion:
            vehiculo = asignacion.vehiculo

            vehiculo_data = {
                "id": vehiculo.id,
                "placa": vehiculo.placa,
                "marca": vehiculo.marca,
                "modelo": vehiculo.modelo,
                "color": vehiculo.color,
                "tipo": (
                    {
                        "id": (
                            vehiculo
                            .tipo_vehiculo_id
                        ),
                        "codigo": (
                            vehiculo
                            .tipo_vehiculo
                            .codigo
                        ),
                        "nombre": (
                            vehiculo
                            .tipo_vehiculo
                            .nombre
                        ),
                    }
                    if vehiculo.tipo_vehiculo_id
                    else None
                ),
            }

        return {
            "id": conductor.id,
            "nombre": conductor.nombre,
            "apellido": conductor.apellido,
            "calificacion": (
                round(float(promedio), 2)
                if promedio is not None
                else 0
            ),
            "total_calificaciones": (
                resumen["total"]
            ),
            "vehiculo": vehiculo_data,
        }

    def get_tiempo_recogida_minutos(
        self,
        oferta,
    ):
        estado = (
            EstadoConductorTiempoReal.objects
            .filter(
                conductor_id=(
                    oferta.conductor_id
                )
            )
            .only(
                "latitud",
                "longitud",
                "ultima_ubicacion",
            )
            .first()
        )

        if (
            not estado
            or estado.latitud is None
            or estado.longitud is None
            or not estado.ultima_ubicacion
        ):
            return None

        viaje = oferta.viaje

        distancia_km = self._distancia_haversine(
            latitud_origen=float(estado.latitud),
            longitud_origen=float(estado.longitud),
            latitud_destino=float(
                viaje.origen_latitud
            ),
            longitud_destino=float(
                viaje.origen_longitud
            ),
        )

        minutos = ceil(
            distancia_km
            / VELOCIDAD_PROMEDIO_RECOGIDA_KMH
            * 60
        )

        return max(1, minutos)

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

        latitud_origen_rad = radians(
            latitud_origen
        )
        latitud_destino_rad = radians(
            latitud_destino
        )

        valor = (
            sin(diferencia_latitud / 2) ** 2
            + cos(latitud_origen_rad)
            * cos(latitud_destino_rad)
            * sin(diferencia_longitud / 2) ** 2
        )

        angulo = 2 * asin(sqrt(valor))

        return radio_tierra_km * angulo
