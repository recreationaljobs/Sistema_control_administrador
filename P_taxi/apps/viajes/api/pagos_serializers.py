"""Serializadores de pagos."""

from rest_framework import serializers

from apps.viajes.models import PagoViaje


class PagoViajeSerializer(
    serializers.ModelSerializer
):
    viaje_id = serializers.UUIDField(
        read_only=True,
    )

    class Meta:
        model = PagoViaje

        fields = [
            "id",
            "viaje_id",
            "metodo",
            "estado",
            "moneda",
            "monto",
            "referencia_externa",
            "proveedor",
            "fecha_pago",
            "fecha_registro",
            "fecha_actualizacion",
        ]

        read_only_fields = fields