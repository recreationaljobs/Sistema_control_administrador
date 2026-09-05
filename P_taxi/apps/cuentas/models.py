"""Modelos de activación, verificación y registro móvil."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def calcular_vencimiento_invitacion():
    return timezone.now() + timedelta(hours=72)


def calcular_vencimiento_codigo():
    return timezone.now() + timedelta(minutes=10)


class InvitacionConductor(models.Model):
    conductor = models.ForeignKey(
        "App_taxi.Conductor",
        on_delete=models.CASCADE,
        related_name="invitaciones_app",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="invitaciones_conductor_creadas",
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_vencimiento = models.DateTimeField(
        default=calcular_vencimiento_invitacion,
    )

    fecha_utilizacion = models.DateTimeField(
        blank=True,
        null=True,
    )

    activa = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = "Invitación de conductor"
        verbose_name_plural = "Invitaciones de conductores"
        ordering = ["-fecha_creacion"]

        indexes = [
            models.Index(
                fields=["token", "activa"],
                name="cuentas_inv_token_activo",
            ),
        ]

    @property
    def utilizada(self):
        return self.fecha_utilizacion is not None

    @property
    def vencida(self):
        return timezone.now() >= self.fecha_vencimiento

    @property
    def es_valida(self):
        return (
            self.activa
            and not self.utilizada
            and not self.vencida
        )

    def marcar_utilizada(self):
        self.fecha_utilizacion = timezone.now()
        self.activa = False

        self.save(
            update_fields=[
                "fecha_utilizacion",
                "activa",
            ]
        )

    def __str__(self):
        return f"{self.conductor} - {self.token}"


class VinculacionConductor(models.Model):
    TIPO_CHOICES = [
        ("empleado", "Empleado"),
        ("afiliado", "Afiliado"),
    ]

    ESTADO_CHOICES = [
        ("activa", "Activa"),
        ("finalizada", "Finalizada"),
    ]

    conductor = models.ForeignKey(
        "App_taxi.Conductor",
        on_delete=models.CASCADE,
        related_name="vinculaciones",
    )

    sucursal = models.ForeignKey(
        "App_taxi.Sucursal",
        on_delete=models.PROTECT,
        related_name="vinculaciones_conductores",
    )

    tipo_vinculacion = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="empleado",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="activa",
        db_index=True,
    )

    fecha_inicio = models.DateTimeField(
        default=timezone.now,
    )

    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
    )

    motivo_fin = models.TextField(
        blank=True,
        default="",
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vinculaciones_creadas",
    )

    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vinculaciones_finalizadas",
    )

    class Meta:
        verbose_name = "Vinculación de conductor"
        verbose_name_plural = "Vinculaciones de conductores"
        ordering = ["-fecha_inicio", "-id"]

    def clean(self):
        super().clean()

        if (
            self.estado == "activa"
            and self.conductor_id
        ):
            vinculacion_existente = (
                VinculacionConductor.objects
                .filter(
                    conductor_id=self.conductor_id,
                    estado="activa",
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if vinculacion_existente:
                raise ValidationError({
                    "conductor": (
                        "Este conductor ya tiene "
                        "una vinculación activa."
                    )
                })

        if (
            self.fecha_fin
            and self.fecha_inicio
            and self.fecha_fin < self.fecha_inicio
        ):
            raise ValidationError({
                "fecha_fin": (
                    "La fecha de finalización no puede "
                    "ser anterior a la fecha de inicio."
                )
            })

    def finalizar(
        self,
        usuario=None,
        motivo="",
    ):
        self.estado = "finalizada"
        self.fecha_fin = timezone.now()
        self.finalizado_por = usuario
        self.motivo_fin = motivo

        self.save(
            update_fields=[
                "estado",
                "fecha_fin",
                "finalizado_por",
                "motivo_fin",
            ]
        )

    def __str__(self):
        return (
            f"{self.conductor} - "
            f"{self.sucursal} - "
            f"{self.get_estado_display()}"
        )


class CodigoRecuperacionPassword(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacion_password",
    )

    codigo_hash = models.CharField(
        max_length=128,
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_vencimiento = models.DateTimeField(
        default=calcular_vencimiento_codigo,
    )

    intentos = models.PositiveSmallIntegerField(
        default=0,
    )

    utilizado = models.BooleanField(
        default=False,
        db_index=True,
    )

    ip_solicitud = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = (
            "Código de recuperación de contraseña"
        )

        verbose_name_plural = (
            "Códigos de recuperación de contraseña"
        )

        ordering = [
            "-fecha_creacion",
        ]

        indexes = [
            models.Index(
                fields=[
                    "usuario",
                    "utilizado",
                    "fecha_vencimiento",
                ],
                name="cuentas_recuperacion_idx",
            ),
        ]

    @property
    def vigente(self):
        return (
            not self.utilizado
            and self.intentos < 5
            and timezone.now()
            < self.fecha_vencimiento
        )

    def __str__(self):
        return (
            f"Recuperación de {self.usuario} - "
            f"{self.fecha_creacion}"
        )