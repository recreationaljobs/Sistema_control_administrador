"""Modelos de disponibilidad y ubicación."""

from decimal import Decimal

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models


class EstadoConductorTiempoReal(
    models.Model
):
    conductor = models.OneToOneField(
        "App_taxi.Conductor",
        on_delete=models.CASCADE,
        related_name="estado_tiempo_real",
    )

    viaje_actual = models.ForeignKey(
        "viajes.Viaje",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estados_conductores",
    )

    en_linea = models.BooleanField(
        default=False,
        db_index=True,
    )

    disponible = models.BooleanField(
        default=False,
        db_index=True,
    )

    latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("-90")
            ),
            MaxValueValidator(
                Decimal("90")
            ),
        ],
    )

    longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("-180")
            ),
            MaxValueValidator(
                Decimal("180")
            ),
        ],
    )

    precision_metros = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0")
            )
        ],
    )

    velocidad_kmh = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0")
            )
        ],
    )

    rumbo_grados = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(
                Decimal("0")
            ),
            MaxValueValidator(
                Decimal("360")
            ),
        ],
    )

    ultima_conexion = models.DateTimeField(
        null=True,
        blank=True,
    )

    ultima_ubicacion = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    fecha_actualizacion = (
        models.DateTimeField(
            auto_now=True,
        )
    )

    class Meta:
        verbose_name = (
            "Estado en tiempo real del conductor"
        )

        verbose_name_plural = (
            "Estados en tiempo real "
            "de conductores"
        )

        ordering = [
            "-ultima_ubicacion",
        ]

        indexes = [
            models.Index(
                fields=[
                    "disponible",
                    "ultima_ubicacion",
                ],
                name="conductor_disponible_idx",
            ),
        ]

    @property
    def tiene_ubicacion(self):
        return (
            self.latitud is not None
            and self.longitud is not None
        )

    def __str__(self):
        estado = (
            "Disponible"
            if self.disponible
            else "No disponible"
        )

        return (
            f"{self.conductor} - {estado}"
        )