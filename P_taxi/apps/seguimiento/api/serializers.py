"""Serializadores de seguimiento."""

from rest_framework import serializers


class DisponibilidadConductorSerializer(
    serializers.Serializer
):
    disponible = serializers.BooleanField()


class UbicacionConductorSerializer(
    serializers.Serializer
):
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

    precision_metros = (
        serializers.DecimalField(
            max_digits=8,
            decimal_places=2,
            min_value=0,
            required=False,
            allow_null=True,
        )
    )

    velocidad_kmh = (
        serializers.DecimalField(
            max_digits=8,
            decimal_places=2,
            min_value=0,
            required=False,
            allow_null=True,
        )
    )

    rumbo_grados = (
        serializers.DecimalField(
            max_digits=6,
            decimal_places=2,
            min_value=0,
            max_value=360,
            required=False,
            allow_null=True,
        )
    )