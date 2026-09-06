"""Serializadores de viajes."""

from rest_framework import serializers
from django.conf import settings
from django.utils import timezone

from apps.flota.models import TipoVehiculo
from apps.pasajeros.models import Pasajero

from ..models import (
    CalificacionViaje,
    OfertaViaje,
    Viaje,
)
from ..services import solicitar_viaje
from django.db.models import (
    Avg,
    Count,
)

def obtener_resumen_calificacion(
    *,
    usuario_id,
    tipo,
):
    if not usuario_id:
        return {
            "promedio": 0,
            "total": 0,
        }

    resultado = (
        CalificacionViaje.objects
        .filter(
            usuario_evaluado_id=usuario_id,
            tipo=tipo,
        )
        .aggregate(
            promedio=Avg("puntuacion"),
            total=Count("id"),
        )
    )

    promedio = resultado["promedio"]

    return {
        "promedio": (
            round(float(promedio), 2)
            if promedio is not None
            else 0
        ),
        "total": resultado["total"],
    }

class ViajeSerializer(
    serializers.ModelSerializer
):
    tipo_vehiculo = serializers.SerializerMethodField()
    pasajero = serializers.SerializerMethodField()
    conductor = serializers.SerializerMethodField()
    vehiculo = serializers.SerializerMethodField()

    class Meta:
        model = Viaje

        fields = [
            "id",
            "pasajero",
            "conductor",
            "vehiculo",
            "tipo_vehiculo",
            "sucursal",
            "estado",
            "origen_direccion",
            "origen_latitud",
            "origen_longitud",
            "destino_direccion",
            "destino_latitud",
            "destino_longitud",
            "distancia_estimada_km",
            "duracion_estimada_minutos",
            "tarifa_estimada",
            "tarifa_acordada",
            "tarifa_final",
            "metodo_pago",
            "notas_pasajero",
            "motivo_cancelacion",
            "cancelado_por",
            "fecha_solicitud",
            "fecha_aceptacion",
            "fecha_llegada_conductor",
            "fecha_inicio",
            "fecha_finalizacion",
            "fecha_cancelacion",
            "fecha_actualizacion",
        ]

        read_only_fields = fields

    def get_tipo_vehiculo(self, obj):
        return {
            "id": obj.tipo_vehiculo_id,
            "codigo": obj.tipo_vehiculo.codigo,
            "nombre": obj.tipo_vehiculo.nombre,
        }

    def get_pasajero(self, obj):
        usuario = obj.pasajero.usuario

        resumen = obtener_resumen_calificacion(
            usuario_id=usuario.id,
            tipo=(
                CalificacionViaje
                .CONDUCTOR_A_PASAJERO
            ),
        )

        return {
            "id": obj.pasajero_id,
            "nombre": usuario.first_name,
            "apellido": usuario.last_name,
            "telefono": usuario.telefono,
            "calificacion": (
                resumen["promedio"]
            ),
            "total_calificaciones": (
                resumen["total"]
            ),
        }

    def get_conductor(self, obj):
        if not obj.conductor:
            return None

        resumen = obtener_resumen_calificacion(
            usuario_id=(
                obj.conductor.usuario_id
            ),
            tipo=(
                CalificacionViaje
                .PASAJERO_A_CONDUCTOR
            ),
        )

        return {
            "id": obj.conductor_id,
            "nombre": obj.conductor.nombre,
            "apellido": obj.conductor.apellido,
            "telefono": obj.conductor.telefono,
            "calificacion": (
                resumen["promedio"]
            ),
            "total_calificaciones": (
                resumen["total"]
            ),
        }

    def get_vehiculo(self, obj):
        if not obj.vehiculo:
            return None

        return {
            "id": obj.vehiculo_id,
            "placa": obj.vehiculo.placa,
            "marca": obj.vehiculo.marca,
            "modelo": obj.vehiculo.modelo,
            "color": obj.vehiculo.color,
        }


class SolicitarViajeSerializer(
    serializers.Serializer
):
    tipo_vehiculo_id = (
        serializers.PrimaryKeyRelatedField(
            source="tipo_vehiculo",
            queryset=(
                TipoVehiculo.objects
                .filter(activo=True)
            ),
        )
    )

    origen_direccion = serializers.CharField(
        max_length=255,
    )

    origen_latitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-90,
        max_value=90,
    )

    origen_longitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-180,
        max_value=180,
    )

    destino_direccion = serializers.CharField(
        max_length=255,
    )

    destino_latitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-90,
        max_value=90,
    )

    destino_longitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-180,
        max_value=180,
    )

    tarifa_propuesta = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=10,
        required=False,
        allow_null=True,
        help_text=(
            "Precio inicial propuesto por el "
            "pasajero. Si no se envía, se utiliza "
            "la tarifa calculada."
        ),
    )

    metodo_pago = serializers.ChoiceField(
        choices=Viaje.METODO_PAGO_CHOICES,
        default="efectivo",
    )

    notas_pasajero = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs):
        request = self.context.get("request")

        pasajero = (
            Pasajero.objects
            .select_related("usuario")
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not pasajero:
            raise serializers.ValidationError({
                "detail": (
                    "La cuenta autenticada no tiene "
                    "un perfil de pasajero."
                )
            })

        origen = (
            attrs["origen_latitud"],
            attrs["origen_longitud"],
        )

        destino = (
            attrs["destino_latitud"],
            attrs["destino_longitud"],
        )

        if origen == destino:
            raise serializers.ValidationError({
                "destino_direccion": (
                    "El destino debe ser diferente "
                    "del punto de origen."
                )
            })

        metodo_pago = attrs.get(
            "metodo_pago",
            "efectivo",
        )

        if (
            metodo_pago == "tarjeta"
            and not getattr(
                settings,
                "PAGOS_TARJETA_HABILITADOS",
                False,
            )
        ):
            raise serializers.ValidationError({
                "metodo_pago": (
                    "Los pagos con tarjeta todavía "
                    "no están disponibles."
                )
            })

        attrs["pasajero"] = pasajero

        return attrs

    def create(self, validated_data):
        try:
            return solicitar_viaje(
                **validated_data
            )
        except Exception as error:
            from django.core.exceptions import ( # type: ignore
                ValidationError as DjangoValidationError,
            )

            if isinstance(
                error,
                DjangoValidationError,
            ):
                raise serializers.ValidationError(
                    error.messages
                )

            raise

class ViajeDisponibleSerializer(
    serializers.ModelSerializer
):
    pasajero_nombre = (
        serializers.SerializerMethodField()
    )

    tipo_vehiculo = (
        serializers.SerializerMethodField()
    )
    pasajero = (
        serializers.SerializerMethodField()
    )
    distancia_recogida_km = (
        serializers.DecimalField(
            max_digits=8,
            decimal_places=2,
            read_only=True,
        )
    )
    mi_oferta = serializers.SerializerMethodField()

    class Meta:
        model = Viaje

        fields = [
            "id",
            "pasajero",
            "pasajero_nombre",
            "tipo_vehiculo",
            "estado",
            "distancia_recogida_km",
            "origen_direccion",
            "origen_latitud",
            "origen_longitud",
            "destino_direccion",
            "destino_latitud",
            "destino_longitud",
            "distancia_estimada_km",
            "duracion_estimada_minutos",
            "tarifa_estimada",
            "tarifa_acordada",
            "mi_oferta",
            "metodo_pago",
            "notas_pasajero",
            "fecha_solicitud",
        ]

        read_only_fields = fields


    def get_pasajero(
        self,
        obj,
    ):
        usuario = obj.pasajero.usuario

        resumen = obtener_resumen_calificacion(
            usuario_id=usuario.id,
            tipo=(
                CalificacionViaje
                .CONDUCTOR_A_PASAJERO
            ),
        )

        return {
            "id": obj.pasajero_id,
            "nombre": usuario.first_name,
            "apellido": usuario.last_name,
            "calificacion": (
                resumen["promedio"]
            ),
            "total_calificaciones": (
                resumen["total"]
            ),
        }
    def get_pasajero_nombre(
        self,
        obj,
    ):
        usuario = obj.pasajero.usuario

        return (
            usuario.first_name
            or "Pasajero"
        )

    def get_tipo_vehiculo(
        self,
        obj,
    ):
        return {
            "id": obj.tipo_vehiculo_id,
            "codigo": (
                obj.tipo_vehiculo.codigo
            ),
            "nombre": (
                obj.tipo_vehiculo.nombre
            ),
        }

    def get_mi_oferta(self, obj):
        conductor = self.context.get(
            "conductor"
        )

        if not conductor:
            return None

        oferta = (
            OfertaViaje.objects
            .filter(
                viaje=obj,
                conductor=conductor,
                estado="pendiente",
                fecha_vencimiento__gt=(
                    timezone.now()
                ),
            )
            .order_by("-fecha_creacion")
            .first()
        )

        if not oferta:
            return None

        return {
            "id": oferta.id,
            "viaje_id": oferta.viaje_id,
            "tarifa_original": (
                oferta.tarifa_original
            ),
            "monto_propuesto": (
                oferta.monto_propuesto
            ),
            "mensaje": oferta.mensaje,
            "estado": oferta.estado,
            "fecha_creacion": (
                oferta.fecha_creacion
            ),
            "fecha_vencimiento": (
                oferta.fecha_vencimiento
            ),
            "fecha_respuesta": (
                oferta.fecha_respuesta
            ),
        }

class CambiarEstadoViajeSerializer(
    serializers.Serializer
):
    estado = serializers.ChoiceField(
        choices=[
            "conductor_en_camino",
            "conductor_llego",
            "en_curso",
            "completado",
        ]
    )

    latitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-90,
        max_value=90,
        required=False,
    )

    longitud = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=-180,
        max_value=180,
        required=False,
    )

    def validate(self, attrs):
        latitud = attrs.get("latitud")
        longitud = attrs.get("longitud")

        if (
            latitud is None
            and longitud is not None
        ) or (
            latitud is not None
            and longitud is None
        ):
            raise serializers.ValidationError(
                "Debes enviar latitud y longitud "
                "juntas."
            )

        return attrs

class CancelarViajeSerializer(
    serializers.Serializer
):
    motivo = serializers.CharField(
        min_length=3,
        max_length=500,
        trim_whitespace=True,
    )
