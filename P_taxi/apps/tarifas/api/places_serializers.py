"""Serializadores para búsqueda de lugares."""

from rest_framework import serializers


class BuscarLugarSerializer(
    serializers.Serializer
):
    consulta = serializers.CharField(
        min_length=3,
        max_length=200,
        trim_whitespace=True,
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

    radio_metros = serializers.IntegerField(
        required=False,
        default=50000,
        min_value=100,
        max_value=50000,
    )

    def validate_consulta(self, value):
        consulta = value.strip()

        if not consulta:
            raise serializers.ValidationError(
                "Debes escribir el lugar "
                "que deseas buscar."
            )

        return consulta