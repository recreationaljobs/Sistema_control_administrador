from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

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
    list_display = ("id", "nombre", "apellido", "cedula", "sucursal", "usuario", "activo")
    search_fields = ("nombre", "apellido", "cedula", "telefono")
    list_filter = ("sucursal", "activo")


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("id", "numero", "placa", "marca", "modelo", "sucursal", "kilometraje_actual", "estado")
    search_fields = ("numero", "placa", "marca", "modelo")
    list_filter = ("sucursal", "estado")


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