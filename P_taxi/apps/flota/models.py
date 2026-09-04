"""Categorías, vinculaciones y habilitaciones de la flota."""

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models


class TipoVehiculo(models.Model):
    codigo = models.CharField(
        max_length=30,
        unique=True,
    )

    nombre = models.CharField(
        max_length=50,
    )

    descripcion = models.CharField(
        max_length=200,
        blank=True,
    )

    capacidad_pasajeros = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(20),
        ],
    )

    permite_equipaje = models.BooleanField(
        default=False,
    )

    requiere_casco = models.BooleanField(
        default=False,
    )

    activo = models.BooleanField(
        default=True,
    )

    orden = models.PositiveSmallIntegerField(
        default=0,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Tipo de vehículo"
        verbose_name_plural = "Tipos de vehículos"
        ordering = [
            "orden",
            "nombre",
        ]

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

