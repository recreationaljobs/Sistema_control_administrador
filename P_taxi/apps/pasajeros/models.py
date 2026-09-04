"""Modelos de pasajeros."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models


class Pasajero(models.Model):
    ESTADO_ACTIVO = "activo"
    ESTADO_SUSPENDIDO = "suspendido"
    ESTADO_BLOQUEADO = "bloqueado"

    ESTADOS = [
        (
            ESTADO_ACTIVO,
            "Activo",
        ),
        (
            ESTADO_SUSPENDIDO,
            "Suspendido",
        ),
        (
            ESTADO_BLOQUEADO,
            "Bloqueado",
        ),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="perfil_pasajero",
    )

    foto = models.ImageField(
        upload_to="pasajeros/perfiles/",
        blank=True,
        null=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_ACTIVO,
    )

    calificacion = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            ),
            MaxValueValidator(
                Decimal("5.00")
            ),
        ],
    )

    total_viajes = models.PositiveIntegerField(
        default=0,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Pasajero"
        verbose_name_plural = "Pasajeros"
        ordering = [
            "-fecha_registro",
        ]

    def __str__(self):
        nombre = self.usuario.get_full_name()

        return (
            nombre
            or self.usuario.username
        )
