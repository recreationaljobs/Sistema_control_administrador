from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from .api.services import procesar_liquidacion_manual
from django.db import transaction
from django.utils import timezone

from .verification_services import (
    aprobar_conductor_completo,
    cambiar_estado_conductor_completo,
)

from .models import (
    Sucursal,
    Rol,
    Usuario,
    EstadoVehiculo,
    EstadoJornada,
    TipoGasto,
    EstadoGasto,
    EstadoAdelanto,
    TipoMantenimiento,
    EstadoMantenimiento,
    Conductor,
    Vehiculo,
    AsignacionVehiculo,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Mantenimiento,
    ConfiguracionSistema,
    Liquidacion,
  
)


class LiquidacionAdminForm(forms.ModelForm):
    liquidar = forms.BooleanField(
        required=False,
        label="Liquidar",
        help_text=(
            "Marca esta casilla para liquidar las jornadas "
            "del conductor dentro del rango seleccionado."
        ),
    )

    class Meta:
        model = Liquidacion
        fields = (
            "sucursal",
            "conductor",
            "usuario",
            "fecha",
            "fecha_inicio",
            "fecha_fin",
            "jornadas_count",
            "total_jornadas",
            "total_adelantos_pendientes",
            "abono_aplicado",
            "ajuste_manual",
            "total_pago",
            "notas",
        )


@admin.register(Liquidacion)
class LiquidacionAdmin(admin.ModelAdmin):
    form = LiquidacionAdminForm

    list_display = (
        "id",
        "conductor",
        "fecha",
        "fecha_inicio",
        "fecha_fin",
        "jornadas_count",
        "total_jornadas",
        "total_pago",
    )

    search_fields = (
        "conductor__nombre",
        "conductor__apellido",
        "conductor__cedula",
    )

    list_filter = (
        "fecha",
        "fecha_inicio",
        "fecha_fin",
    )

    ordering = (
        "-fecha",
        "-id",
    )

    readonly_fields = (
        "jornadas_count",
        "total_jornadas",
        "total_adelantos_pendientes",
        "total_pago",
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        super().save_model(
            request,
            obj,
            form,
            change,
        )

        if not form.cleaned_data.get("liquidar"):
            return

        try:
            resultado = procesar_liquidacion_manual(
                liquidacion=obj,
                usuario=request.user,
            )

            obj.refresh_from_db()

            nivel = (
                messages.SUCCESS
                if resultado.get("procesada")
                else messages.WARNING
            )

            self.message_user(
                request,
                resultado.get(
                    "mensaje",
                    "El proceso de liquidación terminó.",
                ),
                level=nivel,
            )

        except Exception as error:
            self.message_user(
                request,
                (
                    f"No se pudo procesar la liquidación. "
                    f"{type(error).__name__}: {error}"
                ),
                level=messages.ERROR,
            )

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("id", "username", "email", "rol", "sucursal", "is_active", "is_staff")
    list_filter = ("rol", "sucursal", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = UserAdmin.fieldsets + (
        ("Datos del sistema", {
            "fields": ("rol", "sucursal", "telefono")
        }),
    )

    add_fieldsets = (
        UserAdmin.add_fieldsets
        + (
            (
                "Información personal",
                {
                    "classes": (
                        "wide",
                    ),
                    "fields": (
                        "first_name",
                        "last_name",
                        "email",
                        "telefono",
                    ),
                },
            ),
            (
                "Datos del sistema",
                {
                    "classes": (
                        "wide",
                    ),
                    "fields": (
                        "rol",
                        "sucursal",
                        "is_active",
                        "is_staff",
                    ),
                },
            ),
        )
    )


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "propietario", "telefono", "activa", "fecha_registro")
    search_fields = ("nombre", "propietario", "telefono")
    list_filter = ("activa",)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "codigo")
    search_fields = ("nombre", "codigo")


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "apellido",
        "cedula",
        "sucursal",
        "usuario",
        "estado_verificacion",
        "activo",
    )

    search_fields = (
        "nombre",
        "apellido",
        "cedula",
        "telefono",
        "usuario__username",
    )

    list_filter = (
        "estado_verificacion",
        "sucursal",
        "activo",
    )

    actions = (
        "aprobar_conductores",
        "rechazar_conductores",
        "suspender_conductores",
        "marcar_como_pendientes",
    )

    @admin.action(
        description="Aprobar conductores seleccionados"
    )
    def aprobar_conductores(
        self,
        request,
        queryset,
    ):
        cantidad = 0
        errores = []

        for conductor in queryset:
            try:
                aprobar_conductor_completo(
                    conductor.id
                )
                cantidad += 1
            except Exception as error:
                errores.append(
                    f"{conductor}: {error}"
                )

        if cantidad:
            self.message_user(
                request,
                (
                    f"{cantidad} conductor(es), vehículo(s) "
                    "y asignación(es) aprobados correctamente."
                ),
                level=messages.SUCCESS,
            )

        for error in errores:
            self.message_user(
                request,
                error,
                level=messages.ERROR,
            )

    @admin.action(
        description="Rechazar conductores seleccionados"
    )
    def rechazar_conductores(
        self,
        request,
        queryset,
    ):
        cantidad = 0

        for conductor in queryset:
            cambiar_estado_conductor_completo(
                conductor.id,
                "rechazado",
            )
            cantidad += 1

        self.message_user(
            request,
            (
                f"{cantidad} conductor(es) "
                "rechazado(s)."
            ),
            level="warning",
        )

    @admin.action(
        description="Suspender conductores seleccionados"
    )
    def suspender_conductores(
        self,
        request,
        queryset,
    ):
        cantidad = 0

        for conductor in queryset:
            cambiar_estado_conductor_completo(
                conductor.id,
                "suspendido",
            )
            cantidad += 1

        self.message_user(
            request,
            (
                f"{cantidad} conductor(es) "
                "suspendido(s)."
            ),
            level="warning",
        )

    @admin.action(
        description="Marcar conductores como pendientes"
    )
    def marcar_como_pendientes(
        self,
        request,
        queryset,
    ):
        cantidad = 0

        for conductor in queryset:
            cambiar_estado_conductor_completo(
                conductor.id,
                "pendiente",
            )
            cantidad += 1

        self.message_user(
            request,
            (
                f"{cantidad} conductor(es) "
                "marcado(s) como pendiente(s)."
            ),
            level="info",
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        estado = obj.estado_verificacion

        if not change:
            obj.activo = estado == "aprobado"
            super().save_model(
                request,
                obj,
                form,
                change,
            )
            return

        if estado == "aprobado":
            obj.activo = False
            obj.estado_verificacion = "pendiente"
            super().save_model(
                request,
                obj,
                form,
                change,
            )
            aprobar_conductor_completo(obj.id)
            obj.refresh_from_db()
            return

        obj.activo = False
        super().save_model(
            request,
            obj,
            form,
            change,
        )
        cambiar_estado_conductor_completo(
            obj.id,
            estado,
        )


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero",
        "placa",
        "marca",
        "modelo",
        "tipo_vehiculo",
        "tipo_propiedad",
        "propietario_conductor",
        "sucursal",
        "estado_verificacion",
        "estado",
    )

    search_fields = (
        "numero",
        "placa",
        "marca",
        "modelo",
        "propietario_conductor__nombre",
        "propietario_conductor__apellido",
        "propietario_conductor__cedula",
    )

    list_filter = (
        "tipo_vehiculo",
        "tipo_propiedad",
        "estado_verificacion",
        "sucursal",
        "estado",
    )

    raw_id_fields = (
        "propietario_conductor",
    )

    actions = (
        "aprobar_vehiculos_propios",
        "rechazar_vehiculos_propios",
        "suspender_vehiculos_propios",
    )

    @admin.action(
        description=(
            "Aprobar vehículos propios seleccionados"
        )
    )
    def aprobar_vehiculos_propios(
        self,
        request,
        queryset,
    ):
        aprobados = 0
        errores = []

        for vehiculo_original in queryset:
            try:
                with transaction.atomic():
                    vehiculo = (
                        Vehiculo.objects
                        .select_for_update()
                        .select_related(
                            "propietario_conductor",
                            "sucursal",
                        )
                        .get(
                            pk=vehiculo_original.pk
                        )
                    )

                    if (
                        vehiculo.tipo_propiedad
                        != "conductor"
                    ):
                        raise ValueError(
                            "no es un vehículo propio "
                            "de conductor"
                        )

                    if not (
                        vehiculo
                        .propietario_conductor_id
                    ):
                        raise ValueError(
                            "no tiene conductor propietario"
                        )

                    conductor = (
                        Conductor.objects
                        .select_for_update()
                        .get(
                            pk=(
                                vehiculo
                                .propietario_conductor_id
                            )
                        )
                    )

                    if (
                        conductor
                        .estado_verificacion
                        != "aprobado"
                    ):
                        raise ValueError(
                            "el conductor propietario "
                            "no está aprobado"
                        )

                    if not conductor.activo:
                        raise ValueError(
                            "el conductor propietario "
                            "no está activo"
                        )

                    asignacion_conductor = (
                        AsignacionVehiculo.objects
                        .select_for_update()
                        .filter(
                            conductor=conductor,
                            activa=True,
                        )
                        .first()
                    )

                    if (
                        asignacion_conductor
                        and asignacion_conductor
                        .vehiculo_id != vehiculo.id
                    ):
                        raise ValueError(
                            "el conductor ya tiene otro "
                            "vehículo asignado"
                        )

                    asignacion_vehiculo = (
                        AsignacionVehiculo.objects
                        .select_for_update()
                        .filter(
                            vehiculo=vehiculo,
                            activa=True,
                        )
                        .first()
                    )

                    if (
                        asignacion_vehiculo
                        and asignacion_vehiculo
                        .conductor_id != conductor.id
                    ):
                        raise ValueError(
                            "el vehículo ya está asignado "
                            "a otro conductor"
                        )

                    estado_activo = (
                        EstadoVehiculo.objects
                        .filter(
                            codigo="activo",
                            activo=True,
                        )
                        .first()
                    )

                    if not estado_activo:
                        raise ValueError(
                            "no existe el estado de "
                            "vehículo con código activo"
                        )

                    vehiculo.estado_verificacion = (
                        "aprobado"
                    )

                    vehiculo.estado = estado_activo
                    vehiculo.motivo_rechazo = ""

                    vehiculo.save(
                        update_fields=[
                            "estado_verificacion",
                            "estado",
                            "motivo_rechazo",
                        ]
                    )

                    if not asignacion_conductor:
                        AsignacionVehiculo.objects.create(
                            sucursal=vehiculo.sucursal,
                            conductor=conductor,
                            vehiculo=vehiculo,
                            fecha_inicio=(
                                timezone.localdate()
                            ),
                            activa=True,
                        )

                    aprobados += 1

            except Exception as error:
                errores.append(
                    f"{vehiculo_original.placa}: "
                    f"{error}"
                )

        if aprobados:
            self.message_user(
                request,
                (
                    f"{aprobados} vehículo(s) "
                    "aprobado(s) y asignado(s)."
                ),
                level=messages.SUCCESS,
            )

        for error in errores:
            self.message_user(
                request,
                error,
                level=messages.ERROR,
            )

    @admin.action(
        description=(
            "Rechazar vehículos propios seleccionados"
        )
    )
    def rechazar_vehiculos_propios(
        self,
        request,
        queryset,
    ):
        rechazados = 0

        for vehiculo in queryset:
            if (
                vehiculo.tipo_propiedad
                != "conductor"
            ):
                continue

            with transaction.atomic():
                AsignacionVehiculo.objects.filter(
                    vehiculo=vehiculo,
                    activa=True,
                ).update(
                    activa=False,
                    fecha_fin=timezone.localdate(),
                )

                vehiculo.estado_verificacion = (
                    "rechazado"
                )

                vehiculo.estado = None

                if not vehiculo.motivo_rechazo:
                    vehiculo.motivo_rechazo = (
                        "Rechazado desde el panel "
                        "administrativo."
                    )

                vehiculo.save(
                    update_fields=[
                        "estado_verificacion",
                        "estado",
                        "motivo_rechazo",
                    ]
                )

                rechazados += 1

        self.message_user(
            request,
            (
                f"{rechazados} vehículo(s) "
                "rechazado(s)."
            ),
            level=messages.WARNING,
        )

    @admin.action(
        description=(
            "Suspender vehículos propios seleccionados"
        )
    )
    def suspender_vehiculos_propios(
        self,
        request,
        queryset,
    ):
        estado_parqueado = (
            EstadoVehiculo.objects
            .filter(
                codigo="parqueado",
                activo=True,
            )
            .first()
        )

        suspendidos = 0

        for vehiculo in queryset:
            if (
                vehiculo.tipo_propiedad
                != "conductor"
            ):
                continue

            with transaction.atomic():
                AsignacionVehiculo.objects.filter(
                    vehiculo=vehiculo,
                    activa=True,
                ).update(
                    activa=False,
                    fecha_fin=timezone.localdate(),
                )

                vehiculo.estado_verificacion = (
                    "suspendido"
                )

                vehiculo.estado = estado_parqueado

                vehiculo.save(
                    update_fields=[
                        "estado_verificacion",
                        "estado",
                    ]
                )

                suspendidos += 1

        self.message_user(
            request,
            (
                f"{suspendidos} vehículo(s) "
                "suspendido(s) y liberado(s)."
            ),
            level=messages.WARNING,
        )
@admin.register(AsignacionVehiculo)
class AsignacionVehiculoAdmin(admin.ModelAdmin):
    list_display = ("id", "sucursal", "conductor", "vehiculo", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("sucursal", "activa")


@admin.register(JornadaDiaria)
class JornadaDiariaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fecha",
        "sucursal",
        "conductor",
        "vehiculo",
        "ingreso_bruto",
        "pago_conductor",
        "ganancia_dueno",
        "estado",
    )
    search_fields = ("conductor__nombre", "conductor__apellido", "vehiculo__placa")
    list_filter = ("sucursal", "estado", "fecha")


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "sucursal", "vehiculo", "conductor", "tipo_gasto", "monto", "estado")
    list_filter = ("sucursal", "tipo_gasto", "estado", "fecha")


@admin.register(Adelanto)
class AdelantoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "sucursal", "conductor", "monto", "estado")
    list_filter = ("sucursal", "estado", "fecha")


@admin.register(Mantenimiento)
class MantenimientoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "sucursal", "vehiculo", "tipo_mantenimiento", "estado", "kilometraje", "costo")
    list_filter = ("sucursal", "tipo_mantenimiento", "estado", "fecha")


@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sucursal",
        "porcentaje_pago_conductor",
        "intervalo_cambio_aceite_km",
        "intervalo_mantenimiento_km",
        "alerta_previa_km",
        "moneda",
    )


admin.site.register(EstadoVehiculo)
admin.site.register(EstadoJornada)
admin.site.register(TipoGasto)
admin.site.register(EstadoGasto)
admin.site.register(EstadoAdelanto)
admin.site.register(TipoMantenimiento)
admin.site.register(EstadoMantenimiento)
