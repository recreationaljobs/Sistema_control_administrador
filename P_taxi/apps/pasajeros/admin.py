"""Administración de pasajeros."""
from django.contrib import admin

from .models import Pasajero


@admin.register(Pasajero)
class PasajeroAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "estado",
        "calificacion",
        "total_viajes",
        "fecha_registro",
    )

    list_filter = (
        "estado",
        "fecha_registro",
    )

    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__telefono",
        "usuario__email",
    )

    readonly_fields = (
        "calificacion",
        "total_viajes",
        "fecha_registro",
        "fecha_actualizacion",
    )
