"""Modelos del ciclo de vida de los viajes."""

import uuid
from decimal import Decimal

from django.conf import settings # pyright: ignore[reportMissingModuleSource] # pyright: ignore[reportMissingModuleSource]
from django.core.validators import ( # type: ignore
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models # pyright: ignore[reportMissingModuleSource]


class Viaje(models.Model):
    ESTADO_CHOICES = [
        (
            "buscando_conductor",
            "Buscando conductor",
        ),
        (
            "aceptado",
            "Aceptado",
        ),
        (
            "conductor_en_camino",
            "Conductor en camino",
        ),
        (
            "conductor_llego",
            "Conductor llegó",
        ),
        (
            "en_curso",
            "En curso",
        ),
        (
            "completado",
            "Completado",
        ),
        (
            "cancelado",
            "Cancelado",
        ),
        (
            "no_encontrado",
            "Conductor no encontrado",
        ),
    ]

    METODO_PAGO_CHOICES = [
        ("efectivo", "Efectivo"),
        ("tarjeta", "Tarjeta"),
        ("billetera", "Billetera"),
    ]

    CANCELADO_POR_CHOICES = [
        ("pasajero", "Pasajero"),
        ("conductor", "Conductor"),
        ("administrador", "Administrador"),
        ("sistema", "Sistema"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    pasajero = models.ForeignKey(
        "pasajeros.Pasajero",
        on_delete=models.PROTECT,
        related_name="viajes",
    )

    conductor = models.ForeignKey(
        "App_taxi.Conductor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viajes_topo",
    )

    vehiculo = models.ForeignKey(
        "App_taxi.Vehiculo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viajes_topo",
    )

    tipo_vehiculo = models.ForeignKey(
        "flota.TipoVehiculo",
        on_delete=models.PROTECT,
        related_name="viajes",
    )

    cantidad_pasajeros = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(4),
        ],
    )

    sucursal = models.ForeignKey(
        "App_taxi.Sucursal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="viajes_topo",
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default="buscando_conductor",
        db_index=True,
    )

    origen_direccion = models.CharField(
        max_length=255,
    )

    origen_latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        validators=[
            MinValueValidator(
                Decimal("-90")
            ),
            MaxValueValidator(
                Decimal("90")
            ),
        ],
    )

    origen_longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        validators=[
            MinValueValidator(
                Decimal("-180")
            ),
            MaxValueValidator(
                Decimal("180")
            ),
        ],
    )

    destino_direccion = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    destino_latitud = models.DecimalField(
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

    destino_longitud = models.DecimalField(
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

    distancia_estimada_km = (
        models.DecimalField(
            max_digits=8,
            decimal_places=2,
            null=True,
            blank=True,
        )
    )

    duracion_estimada_minutos = (
        models.PositiveIntegerField(
            null=True,
            blank=True,
        )
    )

    tarifa_estimada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    tarifa_acordada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Precio aceptado por el pasajero. "
            "Puede ser la tarifa estimada o "
            "una contraoferta."
        ),
    )

    tarifa_final = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        default="efectivo",
    )

    notas_pasajero = models.TextField(
        blank=True,
        default="",
    )

    motivo_cancelacion = models.TextField(
        blank=True,
        default="",
    )

    cancelado_por = models.CharField(
        max_length=20,
        choices=CANCELADO_POR_CHOICES,
        blank=True,
        default="",
    )

    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_aceptacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_llegada_conductor = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_finalizacion = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    fecha_cancelacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_actualizacion = (
        models.DateTimeField(
            auto_now=True,
        )
    )

    class Meta:
        verbose_name = "Viaje"
        verbose_name_plural = "Viajes"
        ordering = [
            "-fecha_solicitud",
        ]

        indexes = [
            models.Index(
                fields=[
                    "estado",
                    "tipo_vehiculo",
                    "fecha_solicitud",
                ],
                name="viaje_busqueda_idx",
            ),
            models.Index(
                fields=[
                    "pasajero",
                    "estado",
                ],
                name="viaje_pasajero_idx",
            ),
            models.Index(
                fields=[
                    "conductor",
                    "estado",
                ],
                name="viaje_conductor_idx",
            ),
        ]

    @property
    def esta_activo(self):
        return self.estado in [
            "buscando_conductor",
            "aceptado",
            "conductor_en_camino",
            "conductor_llego",
            "en_curso",
        ]

    def __str__(self):
        return (
            f"{self.id} - "
            f"{self.pasajero} - "
            f"{self.get_estado_display()}"
        )


class HistorialEstadoViaje(models.Model):
    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )

    estado_anterior = models.CharField(
        max_length=30,
        choices=Viaje.ESTADO_CHOICES,
        blank=True,
        default="",
    )

    estado_nuevo = models.CharField(
        max_length=30,
        choices=Viaje.ESTADO_CHOICES,
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_estado_viajes",
    )

    observacion = models.TextField(
        blank=True,
        default="",
    )

    latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )

    fecha = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        verbose_name = (
            "Historial de estado del viaje"
        )

        verbose_name_plural = (
            "Historiales de estados de viajes"
        )

        ordering = [
            "fecha",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "viaje",
                    "fecha",
                ],
                name="historial_viaje_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.viaje_id}: "
            f"{self.estado_anterior} → "
            f"{self.estado_nuevo}"
        )

class OfertaViaje(models.Model):
    ESTADOS = [
        (
            "pendiente",
            "Pendiente",
        ),
        (
            "aceptada",
            "Aceptada",
        ),
        (
            "rechazada",
            "Rechazada",
        ),
        (
            "vencida",
            "Vencida",
        ),
        (
            "cancelada",
            "Cancelada",
        ),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.CASCADE,
        related_name="ofertas",
    )

    conductor = models.ForeignKey(
        "App_taxi.Conductor",
        on_delete=models.CASCADE,
        related_name="ofertas_viajes",
    )

    tarifa_original = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    monto_propuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    mensaje = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente",
        db_index=True,
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_vencimiento = models.DateTimeField(
        db_index=True,
    )

    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Oferta de viaje"
        verbose_name_plural = (
            "Ofertas de viajes"
        )

        ordering = [
            "-fecha_creacion",
        ]

        indexes = [
            models.Index(
                fields=[
                    "viaje",
                    "estado",
                ],
                name="oferta_viaje_estado_idx",
            ),
            models.Index(
                fields=[
                    "conductor",
                    "estado",
                ],
                name="oferta_conductor_est_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Oferta {self.id} - "
            f"Viaje {self.viaje_id} - "
            f"C$ {self.monto_propuesto}"
        )

class CalificacionViaje(models.Model):
    PASAJERO_A_CONDUCTOR = (
        "pasajero_a_conductor"
    )

    CONDUCTOR_A_PASAJERO = (
        "conductor_a_pasajero"
    )

    TIPOS = [
        (
            PASAJERO_A_CONDUCTOR,
            "Pasajero califica al conductor",
        ),
        (
            CONDUCTOR_A_PASAJERO,
            "Conductor califica al pasajero",
        ),
    ]

    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.CASCADE,
        related_name="calificaciones",
    )

    tipo = models.CharField(
        max_length=30,
        choices=TIPOS,
    )

    usuario_evaluador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name=(
            "calificaciones_realizadas"
        ),
    )

    usuario_evaluado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name=(
            "calificaciones_recibidas"
        ),
    )

    puntuacion = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )

    comentario = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Calificación de viaje"
        verbose_name_plural = (
            "Calificaciones de viajes"
        )

        ordering = [
            "-fecha_registro",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "viaje",
                    "tipo",
                ],
                name=(
                    "calificacion_unica_"
                    "por_viaje_tipo"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "usuario_evaluado",
                    "tipo",
                ],
                name="calificacion_evaluado_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Viaje {self.viaje_id} - "
            f"{self.puntuacion} estrellas"
        )

class PagoViaje(models.Model):
    METODO_EFECTIVO = "efectivo"
    METODO_TARJETA = "tarjeta"

    METODOS = [
        (
            METODO_EFECTIVO,
            "Efectivo",
        ),
        (
            METODO_TARJETA,
            "Tarjeta",
        ),
    ]

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_PAGADO = "pagado"
    ESTADO_FALLIDO = "fallido"
    ESTADO_CANCELADO = "cancelado"
    ESTADO_REEMBOLSADO = "reembolsado"

    ESTADOS = [
        (
            ESTADO_PENDIENTE,
            "Pendiente",
        ),
        (
            ESTADO_PAGADO,
            "Pagado",
        ),
        (
            ESTADO_FALLIDO,
            "Fallido",
        ),
        (
            ESTADO_CANCELADO,
            "Cancelado",
        ),
        (
            ESTADO_REEMBOLSADO,
            "Reembolsado",
        ),
    ]

    viaje = models.OneToOneField(
        Viaje,
        on_delete=models.PROTECT,
        related_name="pago",
    )

    metodo = models.CharField(
        max_length=20,
        choices=METODOS,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE,
        db_index=True,
    )

    moneda = models.CharField(
        max_length=10,
        default="NIO",
    )

    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    referencia_externa = models.CharField(
        max_length=150,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Referencia futura de la "
            "pasarela de tarjetas."
        ),
    )

    proveedor = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text=(
            "Proveedor futuro del pago "
            "con tarjeta."
        ),
    )

    datos_proveedor = models.JSONField(
        default=dict,
        blank=True,
    )

    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "pagos_viajes_confirmados"
        ),
    )

    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Pago de viaje"
        verbose_name_plural = (
            "Pagos de viajes"
        )

        ordering = [
            "-fecha_registro",
        ]

        indexes = [
            models.Index(
                fields=[
                    "metodo",
                    "estado",
                ],
                name="pago_metodo_estado_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Pago del viaje {self.viaje_id} - "
            f"{self.metodo} - {self.estado}"
        )
