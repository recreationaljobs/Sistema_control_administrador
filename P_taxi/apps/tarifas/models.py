"""Modelos de tarifas y comisiones."""

from decimal import Decimal

from django.core.exceptions import (
    ValidationError,
)
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone


class TarifaVehiculo(models.Model):
    nombre = models.CharField(
        max_length=100,
    )

    tipo_vehiculo = models.ForeignKey(
        "flota.TipoVehiculo",
        on_delete=models.PROTECT,
        related_name="tarifas",
    )

    sucursal = models.ForeignKey(
        "App_taxi.Sucursal",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tarifas_topo",
        help_text=(
            "Vacío significa que la tarifa "
            "es global."
        ),
    )

    moneda = models.CharField(
        max_length=10,
        default="NIO",
    )

    tarifa_base = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0")
            )
        ],
    )

    precio_por_km = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0")
            )
        ],
    )

    tarifa_minima = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0")
            )
        ],
    )

    factor_distancia_ruta = (
        models.DecimalField(
            max_digits=5,
            decimal_places=2,
            default=Decimal("1.25"),
            validators=[
                MinValueValidator(
                    Decimal("1.00")
                ),
                MaxValueValidator(
                    Decimal("3.00")
                ),
            ],
            help_text=(
                "Corrige la distancia en línea "
                "recta para aproximar la ruta real."
            ),
        )
    )

    porcentaje_comision_plataforma = (
        models.DecimalField(
            max_digits=5,
            decimal_places=2,
            default=Decimal("10.00"),
            validators=[
                MinValueValidator(
                    Decimal("0")
                ),
                MaxValueValidator(
                    Decimal("100")
                ),
            ],
        )
    )

    activo = models.BooleanField(
        default=True,
        db_index=True,
    )

    vigencia_desde = models.DateTimeField(
        default=timezone.now,
    )

    vigencia_hasta = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = (
        models.DateTimeField(
            auto_now=True,
        )
    )

    class Meta:
        verbose_name = (
            "Tarifa de vehículo"
        )

        verbose_name_plural = (
            "Tarifas de vehículos"
        )

        ordering = [
            "tipo_vehiculo__orden",
            "sucursal_id",
            "-vigencia_desde",
        ]

        indexes = [
            models.Index(
                fields=[
                    "tipo_vehiculo",
                    "sucursal",
                    "activo",
                ],
                name="tarifa_tipo_sucursal_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.vigencia_hasta
            and self.vigencia_hasta
            <= self.vigencia_desde
        ):
            raise ValidationError({
                "vigencia_hasta": (
                    "La fecha final debe ser "
                    "posterior a la fecha inicial."
                )
            })

        if (
            self.tarifa_minima
            < self.tarifa_base
        ):
            raise ValidationError({
                "tarifa_minima": (
                    "La tarifa mínima no puede ser "
                    "menor que la tarifa base."
                )
            })

        if self.activo:
            tarifa_duplicada = (
                TarifaVehiculo.objects
                .filter(
                    tipo_vehiculo=(
                        self.tipo_vehiculo
                    ),
                    sucursal=self.sucursal,
                    activo=True,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if tarifa_duplicada:
                raise ValidationError(
                    "Ya existe una tarifa activa "
                    "para este tipo de vehículo "
                    "y sucursal."
                )

    def __str__(self):
        alcance = (
            self.sucursal.nombre
            if self.sucursal
            else "Global"
        )

        return (
            f"{self.nombre} - "
            f"{self.tipo_vehiculo.nombre} - "
            f"{alcance}"
        )