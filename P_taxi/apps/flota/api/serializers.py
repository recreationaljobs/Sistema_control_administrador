"""Serializadores de flota."""

from datetime import date

from rest_framework import serializers

from App_taxi.models import (
    Conductor,
    Vehiculo,
)

from ..models import TipoVehiculo


class TipoVehiculoSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = TipoVehiculo

        fields = [
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "capacidad_pasajeros",
            "permite_equipaje",
            "requiere_casco",
            "activo",
            "orden",
            "fecha_registro",
            "fecha_actualizacion",
        ]

        read_only_fields = [
            "id",
            "fecha_registro",
            "fecha_actualizacion",
        ]

    def validate_codigo(self, value):
        codigo = value.strip().lower()

        if not codigo:
            raise serializers.ValidationError(
                "El código del tipo de vehículo "
                "es obligatorio."
            )

        return codigo


class RegistroVehiculoPropioSerializer(
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

    placa = serializers.CharField(
        max_length=20,
    )

    marca = serializers.CharField(
        max_length=50,
    )

    modelo = serializers.CharField(
        max_length=50,
    )

    anio = serializers.IntegerField(
        min_value=1900,
        max_value=date.today().year + 1,
    )

    color = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
    )

    numero_motor = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    numero_chasis = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    tipo_combustible = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
    )

    kilometraje_actual = (
        serializers.IntegerField(
            min_value=0,
            required=False,
            default=0,
        )
    )

    def validate_placa(self, value):
        placa = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "")
        )

        if not placa:
            raise serializers.ValidationError(
                "La placa es obligatoria."
            )

        if Vehiculo.objects.filter(
            placa__iexact=placa
        ).exists():
            raise serializers.ValidationError(
                "Ya existe un vehículo registrado "
                "con esta placa."
            )

        return placa

    def validate(self, attrs):
        request = self.context.get("request")
        usuario = getattr(
            request,
            "user",
            None,
        )

        if (
            not usuario
            or not usuario.is_authenticated
        ):
            raise serializers.ValidationError({
                "detail": (
                    "Debes iniciar sesión."
                )
            })

        conductor = (
            Conductor.objects
            .select_related(
                "usuario",
                "sucursal",
            )
            .filter(
                usuario=usuario
            )
            .first()
        )

        if not conductor:
            raise serializers.ValidationError({
                "detail": (
                    "La cuenta no tiene un perfil "
                    "de conductor vinculado."
                )
            })

        if (
            conductor.estado_verificacion
            != "aprobado"
        ):
            raise serializers.ValidationError({
                "detail": (
                    "El conductor debe estar aprobado "
                    "antes de registrar un vehículo."
                )
            })

        if not conductor.activo:
            raise serializers.ValidationError({
                "detail": (
                    "El perfil del conductor "
                    "no está activo."
                )
            })

        vehiculo_existente = (
            Vehiculo.objects
            .filter(
                propietario_conductor=conductor
            )
            .exclude(
                estado_verificacion="rechazado"
            )
            .exists()
        )

        if vehiculo_existente:
            raise serializers.ValidationError({
                "detail": (
                    "Ya tienes un vehículo propio "
                    "registrado o pendiente."
                )
            })

        attrs["conductor"] = conductor

        return attrs

    def create(self, validated_data):
        conductor = validated_data.pop(
            "conductor"
        )

        tipo_vehiculo = validated_data.pop(
            "tipo_vehiculo"
        )

        placa = validated_data["placa"]

        vehiculo = Vehiculo.objects.create(
            sucursal=conductor.sucursal,
            estado=None,
            tipo_vehiculo=tipo_vehiculo,
            tipo_propiedad="conductor",
            propietario_conductor=conductor,
            estado_verificacion="pendiente",
            motivo_rechazo="",
            numero=placa,
            placa=placa,
            marca=validated_data["marca"],
            modelo=validated_data["modelo"],
            anio=validated_data["anio"],
            color=validated_data.get(
                "color",
                "",
            ),
            numero_motor=validated_data.get(
                "numero_motor",
                "",
            ),
            numero_chasis=validated_data.get(
                "numero_chasis",
                "",
            ),
            tipo_combustible=(
                validated_data.get(
                    "tipo_combustible",
                    "",
                )
            ),
            kilometraje_actual=(
                validated_data.get(
                    "kilometraje_actual",
                    0,
                )
            ),
        )

        return vehiculo