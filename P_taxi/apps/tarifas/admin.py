"""Administración de tarifas."""

from django.contrib import admin

from .models import TarifaVehiculo


@admin.register(TarifaVehiculo)
class TarifaVehiculoAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "nombre",
        "tipo_vehiculo",
        "sucursal",
        "moneda",
        "tarifa_base",
        "precio_por_km",
        "tarifa_minima",
        "factor_distancia_ruta",
        "porcentaje_comision_plataforma",
        "activo",
        "vigencia_desde",
    )

    search_fields = (
        "nombre",
        "tipo_vehiculo__nombre",
        "tipo_vehiculo__codigo",
        "sucursal__nombre",
    )

    list_filter = (
        "activo",
        "tipo_vehiculo",
        "sucursal",
        "moneda",
    )

    readonly_fields = (
        "fecha_registro",
        "fecha_actualizacion",
    )