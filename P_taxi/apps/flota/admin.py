"""Administración de la flota multimodal."""


from django.contrib import admin

from .models import TipoVehiculo


@admin.register(TipoVehiculo)
class TipoVehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "codigo",
        "capacidad_pasajeros",
        "requiere_casco",
        "permite_equipaje",
        "activo",
        "orden",
    )

    list_filter = (
        "activo",
        "requiere_casco",
        "permite_equipaje",
    )

    search_fields = (
        "nombre",
        "codigo",
    )

    ordering = (
        "orden",
        "nombre",
    )