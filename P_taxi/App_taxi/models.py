from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Sucursal(models.Model):
    nombre = models.CharField(max_length=150)
    propietario = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    nombre = models.CharField(max_length=80)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    rol = models.ForeignKey(
        Rol,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="usuarios"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="usuarios"
    )

    telefono = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-id"]

    def __str__(self):
        rol_nombre = self.rol.nombre if self.rol else "Sin rol"
        return f"{self.username} - {rol_nombre}"


class EstadoVehiculo(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estado de vehículo"
        verbose_name_plural = "Estados de vehículos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoJornada(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)


    class Meta:
        verbose_name = "Estado de jornada"
        verbose_name_plural = "Estados de jornadas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoGasto(models.Model):
    nombre = models.CharField(max_length=80)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de gasto"
        verbose_name_plural = "Tipos de gastos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoGasto(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Estado de gasto"
        verbose_name_plural = "Estados de gastos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoAdelanto(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estado de adelanto"
        verbose_name_plural = "Estados de adelantos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoMantenimiento(models.Model):
    nombre = models.CharField(max_length=80)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)
    intervalo_km = models.PositiveIntegerField(default=5000)

    class Meta:
        verbose_name = "Tipo de mantenimiento"
        verbose_name_plural = "Tipos de mantenimientos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoMantenimiento(models.Model):
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=50, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estado de mantenimiento"
        verbose_name_plural = "Estados de mantenimientos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Conductor(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="conductores",
        null=True,
        blank=True
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_conductor"
    )

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    cedula = models.CharField(max_length=30)
    direccion = models.TextField(blank=True, null=True)
    numero_licencia = models.CharField(max_length=50, blank=True, null=True)
    fecha_inicio_licencia = models.DateField(blank=True, null=True)
    fecha_vencimiento_licencia = models.DateField(blank=True, null=True)

    porcentaje_pago = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00"))
        ]
    )

    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Conductor"
        verbose_name_plural = "Conductores"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "cedula"],
                name="unique_cedula_conductor_por_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Vehiculo(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="vehiculos"
       
    )

    estado = models.ForeignKey(
        EstadoVehiculo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="vehiculos"
    )

    numero = models.CharField(max_length=20)
    placa = models.CharField(max_length=20, unique=True)
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    anio = models.PositiveIntegerField()
    color = models.CharField(max_length=30, blank=True, null=True)
    numero_motor = models.CharField(max_length=100, blank=True, null=True)
    numero_chasis = models.CharField(max_length=100, blank=True, null=True)
    tipo_combustible = models.CharField(max_length=30, blank=True, null=True)

    kilometraje_actual = models.PositiveIntegerField(default=0)

    km_ultimo_cambio_aceite = models.PositiveIntegerField(default=0)
    km_intervalo_cambio_aceite = models.PositiveIntegerField(default=5000)

    km_ultimo_mantenimiento = models.PositiveIntegerField(default=0)
    km_intervalo_mantenimiento = models.PositiveIntegerField(default=10000)

    alerta_previa_km = models.PositiveIntegerField(default=300)

    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ["placa"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "numero"],
                name="unique_numero_vehiculo_por_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.numero} - {self.placa}"


class AsignacionVehiculo(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="asignaciones"
    )

    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name="asignaciones"
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="asignaciones"
    )

    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(blank=True, null=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Asignación de vehículo"
        verbose_name_plural = "Asignaciones de vehículos"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehiculo"],
                condition=Q(activa=True),
                name="unique_vehiculo_activo"
            ),
            models.UniqueConstraint(
                fields=["conductor"],
                condition=Q(activa=True),
                name="unique_conductor_activo"
            ),
        ]

    def clean(self):
        super().clean()

        # Solo las asignaciones activas compiten por vehículo/conductor.
        if not self.activa:
            return

        conflicto_vehiculo = (
            AsignacionVehiculo.objects
            .filter(vehiculo=self.vehiculo, activa=True)
            .exclude(pk=self.pk)
            .select_related("conductor")
            .first()
        )
        if conflicto_vehiculo:
            c = conflicto_vehiculo.conductor
            raise ValidationError(
                f"El vehículo {self.vehiculo.placa} ya está asignado al conductor "
                f"{c.nombre} {c.apellido}."
            )

        conflicto_conductor = (
            AsignacionVehiculo.objects
            .filter(conductor=self.conductor, activa=True)
            .exclude(pk=self.pk)
            .select_related("vehiculo")
            .first()
        )
        if conflicto_conductor:
            raise ValidationError(
                f"El conductor {self.conductor.nombre} {self.conductor.apellido} "
                f"ya tiene otro vehículo asignado ({conflicto_conductor.vehiculo.placa})."
            )

    def __str__(self):
        return f"{self.conductor} - {self.vehiculo.placa}"


class JornadaDiaria(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="jornadas"
    )

    estado = models.ForeignKey(
        EstadoJornada,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="jornadas"
    )

    fecha = models.DateField(default=timezone.localdate)

    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name="jornadas"
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="jornadas"
    )

    TIPO_COBRO_CHOICES = [
        ("porcentaje", "Porcentaje"),
        ("alquiler", "Alquiler"),
    ]

    kilometraje_inicial = models.PositiveIntegerField()

    kilometraje_final = models.PositiveIntegerField(
    blank=True,
    null=True
)

    kilometros_recorridos = models.PositiveIntegerField(default=0)

    tipo_cobro = models.CharField(
    max_length=20,
    choices=TIPO_COBRO_CHOICES,
    default="porcentaje"
)

    ingreso_bruto = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=Decimal("0.00")
)

    monto_alquiler = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=Decimal("0.00"),
    validators=[MinValueValidator(Decimal("0.00"))]
)

    porcentaje_pago_conductor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00"))
        ]
    )

    pago_conductor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_adelantos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    pago_pendiente_conductor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    saldo_adelanto_excedente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_gastos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    ganancia_dueno = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jornada diaria"
        verbose_name_plural = "Jornadas diarias"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["fecha", "conductor", "vehiculo"],
                name="unique_jornada_por_fecha_conductor_vehiculo"
            )
        ]

    def __str__(self):
        return f"{self.fecha} - {self.conductor} - {self.vehiculo.placa}"


class Gasto(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="gastos"
    )

    jornada = models.ForeignKey(
        JornadaDiaria,
        on_delete=models.CASCADE,
        related_name="gastos",
        blank=True,
        null=True
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="gastos"
    )

    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.SET_NULL,
        related_name="gastos",
        blank=True,
        null=True
    )

    tipo_gasto = models.ForeignKey(
        TipoGasto,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="gastos"
    )

    estado = models.ForeignKey(
        EstadoGasto,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="gastos"
    )

    descripcion = models.TextField(blank=True, null=True)

    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    fecha = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        tipo = self.tipo_gasto.nombre if self.tipo_gasto else "Gasto"
        return f"{tipo} - {self.monto}"


class Adelanto(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        related_name="adelantos",
        blank=True,
        null=True
    )

    jornada = models.ForeignKey(
    JornadaDiaria,
    on_delete=models.SET_NULL,
    related_name="adelantos",
    blank=True,
    null=True
)
    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name="adelantos"
    )

    estado = models.ForeignKey(
        EstadoAdelanto,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="adelantos"
    )

    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    fecha = models.DateField(default=timezone.localdate)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Adelanto"
        verbose_name_plural = "Adelantos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"Adelanto {self.monto} - {self.conductor}"


class Mantenimiento(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="mantenimientos",
        blank=True,
        null=True,
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="mantenimientos"
    )

    tipo_mantenimiento = models.ForeignKey(
        TipoMantenimiento,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mantenimientos"
    )

    estado = models.ForeignKey(
        EstadoMantenimiento,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mantenimientos"
    )

    descripcion = models.TextField(blank=True, null=True)

    costo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    fecha = models.DateField(default=timezone.localdate)
    kilometraje = models.PositiveIntegerField()
    proximo_km_sugerido = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Mantenimiento"
        verbose_name_plural = "Mantenimientos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        tipo = self.tipo_mantenimiento.nombre if self.tipo_mantenimiento else "Mantenimiento"
        return f"{self.vehiculo.placa} - {tipo}"


class ConfiguracionSistema(models.Model):
    sucursal = models.OneToOneField(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="configuracion",
        blank=True,
        null=True
    )

    porcentaje_pago_conductor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00"))
        ]
    )

    intervalo_cambio_aceite_km = models.PositiveIntegerField(default=5000)
    intervalo_mantenimiento_km = models.PositiveIntegerField(default=10000)
    alerta_previa_km = models.PositiveIntegerField(default=300)

    # Km antes del punto de cambio en que se dispara el aviso de aceite.
    km_aviso_mantenimiento = models.PositiveIntegerField(default=30)

    moneda = models.CharField(max_length=10, default="C$")

    class Meta:
        verbose_name = "Configuración del sistema"
        verbose_name_plural = "Configuraciones del sistema"

    def __str__(self):
        if self.sucursal:
            return f"Configuración - {self.sucursal.nombre}"
        return "Configuración global"

class Liquidacion(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="liquidaciones"
    )

    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name="liquidaciones"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="liquidaciones_registradas"
    )

    fecha = models.DateField(default=timezone.localdate)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)

    jornadas_count = models.PositiveIntegerField(default=0)

    total_jornadas = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_adelantos_pendientes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    abono_aplicado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    ajuste_manual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_pago = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notas = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Liquidación"
        verbose_name_plural = "Liquidaciones"
        ordering = ["-fecha_registro", "-id"]

    def __str__(self):
        return f"Liquidación #{self.id} - {self.conductor}"


class DetalleLiquidacion(models.Model):
    liquidacion = models.ForeignKey(
        Liquidacion,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    jornada = models.ForeignKey(
        JornadaDiaria,
        on_delete=models.PROTECT,
        related_name="detalles_liquidacion"
    )

    fecha = models.DateField()
    vehiculo = models.CharField(max_length=150, blank=True, null=True)

    kilometros_recorridos = models.PositiveIntegerField(default=0)

    ingreso_bruto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    pago_conductor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    class Meta:
        verbose_name = "Detalle de liquidación"
        verbose_name_plural = "Detalles de liquidación"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"Liquidación #{self.liquidacion_id} - Jornada #{self.jornada_id}"
    

class DispositivoNotificacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dispositivos_notificacion",
    )

    token = models.CharField(
        max_length=512,
        unique=True,
    )

    activo = models.BooleanField(
        default=True
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.usuario.username} - "
            f"{'Activo' if self.activo else 'Inactivo'}"
        )


class RegistroNotificacion(models.Model):
    TIPO_APERTURA = "JORNADA_NO_INICIADA"
    TIPO_CIERRE = "JORNADA_NO_CERRADA"

    TIPOS = [
        (
            TIPO_APERTURA,
            "Jornada no iniciada",
        ),
        (
            TIPO_CIERRE,
            "Jornada no cerrada",
        ),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registros_notificacion",
    )

    tipo = models.CharField(
        max_length=40,
        choices=TIPOS,
    )

    fecha_jornada = models.DateField()

    titulo = models.CharField(
        max_length=150
    )

    mensaje = models.TextField()

    enviada = models.BooleanField(
        default=False
    )

    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "usuario",
                    "tipo",
                    "fecha_jornada",
                ],
                name=(
                    "notificacion_jornada_"
                    "unica_por_usuario"
                ),
            )
        ]

    def __str__(self):
        return (
            f"{self.usuario.username} - "
            f"{self.tipo} - "
            f"{self.fecha_jornada}"
        )
    

class RegistroNotificacionMantenimiento(
    models.Model
):
    TIPO_ACEITE_PROXIMO = (
        "CAMBIO_ACEITE_PROXIMO"
    )

    TIPO_ACEITE_VENCIDO = (
        "CAMBIO_ACEITE_VENCIDO"
    )

    TIPOS = [
        (
            TIPO_ACEITE_PROXIMO,
            "Cambio de aceite próximo",
        ),
        (
            TIPO_ACEITE_VENCIDO,
            "Cambio de aceite vencido",
        ),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name=(
            "registros_notificacion_"
            "mantenimiento"
        ),
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name=(
            "registros_notificacion_"
            "mantenimiento"
        ),
    )

    tipo = models.CharField(
        max_length=40,
        choices=TIPOS,
    )

    kilometraje_objetivo = (
        models.PositiveIntegerField()
    )

    kilometraje_detectado = (
        models.PositiveIntegerField()
    )

    titulo = models.CharField(
        max_length=150
    )

    mensaje = models.TextField()

    enviada = models.BooleanField(
        default=False
    )

    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = (
            "Registro de notificación "
            "de mantenimiento"
        )

        verbose_name_plural = (
            "Registros de notificaciones "
            "de mantenimiento"
        )

        ordering = [
            "-fecha_creacion",
            "-id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "usuario",
                    "vehiculo",
                    "tipo",
                    "kilometraje_objetivo",
                ],
                name=(
                    "notif_mant_unica_"
                    "usuario_vehiculo_tipo_km"
                ),
            )
        ]

    def __str__(self):
        return (
            f"{self.usuario.username} - "
            f"{self.vehiculo.placa} - "
            f"{self.tipo} - "
            f"{self.kilometraje_objetivo} km"
        )
    
class DocumentoVehiculo(models.Model):
    TIPO_INSPECCION_MECANICA = "inspeccion_mecanica"
    TIPO_EMISION_GASES = "emision_gases"
    TIPO_SEGURO_VEHICULAR = "seguro_vehicular"
    TIPO_SEGURO_PASAJERO = "seguro_pasajero"

    TIPO_DOCUMENTO_CHOICES = [
        (
            TIPO_INSPECCION_MECANICA,
            "Inspección mecánica",
        ),
        (
            TIPO_EMISION_GASES,
            "Emisión de gases",
        ),
        (
            TIPO_SEGURO_VEHICULAR,
            "Seguro vehicular",
        ),
        (
            TIPO_SEGURO_PASAJERO,
            "Seguro de pasajero",
        ),
    ]

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="documentos",
    )

    tipo_documento = models.CharField(
        max_length=40,
        choices=TIPO_DOCUMENTO_CHOICES,
    )

    fecha_inicio = models.DateField()

    fecha_vencimiento = models.DateField()

    observaciones = models.TextField(
        blank=True,
        null=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Documento de vehículo"
        verbose_name_plural = "Documentos de vehículos"

        ordering = [
            "-fecha_vencimiento",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "vehiculo",
                    "tipo_documento",
                ],
                name="doc_veh_tipo_idx",
            ),
            models.Index(
                fields=[
                    "fecha_vencimiento",
                ],
                name="doc_fecha_venc_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.fecha_inicio
            and self.fecha_vencimiento
            and self.fecha_vencimiento < self.fecha_inicio
        ):
            raise ValidationError({
                "fecha_vencimiento": (
                    "La fecha de vencimiento no puede ser "
                    "anterior a la fecha de inicio."
                )
            })

    @property
    def dias_para_vencer(self):
        if not self.fecha_vencimiento:
            return None

        hoy = timezone.localdate()

        return (
            self.fecha_vencimiento - hoy
        ).days

    @property
    def estado_documento(self):
        dias = self.dias_para_vencer

        if dias is None:
            return "sin_registrar"

        if dias < 0:
            return "vencido"

        if dias <= 30:
            return "por_vencer"

        return "vigente"

    @property
    def estado_documento_nombre(self):
        estados = {
            "vigente": "Vigente",
            "por_vencer": "Por vencer",
            "vencido": "Vencido",
            "sin_registrar": "Sin registrar",
        }

        return estados.get(
            self.estado_documento,
            "Sin registrar",
        )

    def __str__(self):
        return (
            f"{self.get_tipo_documento_display()} - "
            f"{self.vehiculo.numero} - "
            f"{self.vehiculo.placa}"
        )
