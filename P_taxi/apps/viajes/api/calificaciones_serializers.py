"""Serializadores de calificaciones."""

from rest_framework import serializers

from apps.viajes.models import (
    CalificacionViaje,
)


class CrearCalificacionSerializer(
    serializers.Serializer
):
    puntuacion = serializers.IntegerField(
        min_value=1,
        max_value=5,
    )

    comentario = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )


class CalificacionViajeSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = CalificacionViaje

        fields = [
            "id",
            "viaje",
            "tipo",
            "puntuacion",
            "comentario",
            "fecha_registro",
        ]

        read_only_fields = fields