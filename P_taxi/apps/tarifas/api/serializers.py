"""Serializadores de tarifas."""

from rest_framework import serializers

from apps.flota.models import (
    TipoVehiculo,
)


class CoordenadasRutaSerializer(
    serializers.Serializer
):
    origen_latitud = (
        serializers.DecimalField(
            max_digits=10,
            decimal_places=7,
            min_value=-90,
            max_value=90,
        )
    )

    origen_longitud = (
        serializers.DecimalField(
            max_digits=10,
            decimal_places=7,
            min_value=-180,
            max_value=180,
        )
    )

    destino_latitud = (
        serializers.DecimalField(
            max_digits=10,
            decimal_places=7,
            min_value=-90,
            max_value=90,
        )
    )

    destino_longitud = (
        serializers.DecimalField(
            max_digits=10,
            decimal_places=7,
            min_value=-180,
            max_value=180,
        )
    )

    def validate(self, attrs):
        origen = (
            attrs["origen_latitud"],
            attrs["origen_longitud"],
        )

        destino = (
            attrs["destino_latitud"],
            attrs["destino_longitud"],
        )

        if origen == destino:
            raise serializers.ValidationError(
                "El origen y el destino deben "
                "ser diferentes."
            )

        return attrs


class EstimarTarifaSerializer(
    CoordenadasRutaSerializer
):
    tipo_vehiculo_id = (
        serializers
        .PrimaryKeyRelatedField(
            source="tipo_vehiculo",
            queryset=(
                TipoVehiculo.objects
                .filter(activo=True)
            ),
        )
    )


class CalcularRutaSerializer(
    CoordenadasRutaSerializer
):
    pass