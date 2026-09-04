"""Administración de viajes y contraofertas."""

from django.contrib import admin

from .models import (
    CalificacionViaje,
    HistorialEstadoViaje,
    OfertaViaje,
    Viaje,
    PagoViaje,
)



@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "pasajero",
        "conductor",
        "tipo_vehiculo",
        "estado",
        "tarifa_estimada",
        "tarifa_acordada",
        "tarifa_final",
        "fecha_solicitud",
    ]

    list_filter = [
        "estado",
        "tipo_vehiculo",
        "metodo_pago",
        "fecha_solicitud",
    ]

    search_fields = [
        "id",
        "pasajero__nombre",
        "pasajero__apellido",
        "pasajero__telefono",
        "conductor__nombre",
        "conductor__apellido",
        "conductor__telefono",
        "origen_direccion",
        "destino_direccion",
    ]

    ordering = [
        "-fecha_solicitud",
    ]

    list_select_related = [
        "pasajero",
        "conductor",
        "vehiculo",
        "tipo_vehiculo",
        "sucursal",
    ]

    readonly_fields = [
        "id",
        "fecha_solicitud",
        "fecha_actualizacion",
    ]


@admin.register(OfertaViaje)
class OfertaViajeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "viaje",
        "conductor",
        "tarifa_original",
        "monto_propuesto",
        "estado",
        "fecha_creacion",
        "fecha_vencimiento",
        "fecha_respuesta",
    ]

    list_filter = [
        "estado",
        "fecha_creacion",
        "fecha_vencimiento",
    ]

    search_fields = [
        "id",
        "viaje__id",
        "conductor__nombre",
        "conductor__apellido",
        "conductor__telefono",
        "mensaje",
    ]

    ordering = [
        "-fecha_creacion",
    ]

    list_select_related = [
        "viaje",
        "conductor",
    ]

    readonly_fields = [
        "id",
        "fecha_creacion",
        "fecha_actualizacion",
    ]


@admin.register(HistorialEstadoViaje)
class HistorialEstadoViajeAdmin(
    admin.ModelAdmin
):
    list_display = [
        "id",
        "viaje",
        "estado_anterior",
        "estado_nuevo",
        "usuario",
    ]

    list_filter = [
        "estado_nuevo",
    ]

    search_fields = [
        "viaje__id",
        "estado_anterior",
        "estado_nuevo",
        "observacion",
        "usuario__username",
    ]

    list_select_related = [
        "viaje",
        "usuario",
    ]
@admin.register(CalificacionViaje)
class CalificacionViajeAdmin(
    admin.ModelAdmin
):
    list_display = [
        "id",
        "viaje",
        "tipo",
        "usuario_evaluador",
        "usuario_evaluado",
        "puntuacion",
        "fecha_registro",
    ]

    list_filter = [
        "tipo",
        "puntuacion",
        "fecha_registro",
    ]

    search_fields = [
        "viaje__id",
        "usuario_evaluador__username",
        "usuario_evaluado__username",
        "comentario",
    ]

    list_select_related = [
        "viaje",
        "usuario_evaluador",
        "usuario_evaluado",
    ]

    ordering = [
        "-fecha_registro",
    ]

    readonly_fields = [
        "fecha_registro",
        "fecha_actualizacion",
    ]

@admin.register(PagoViaje)
class PagoViajeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "viaje",
        "metodo",
        "estado",
        "moneda",
        "monto",
        "confirmado_por",
        "fecha_pago",
        "fecha_registro",
    ]

    list_filter = [
        "metodo",
        "estado",
        "fecha_pago",
        "fecha_registro",
    ]

    search_fields = [
        "viaje__id",
        "referencia_externa",
        "confirmado_por__username",
    ]

    list_select_related = [
        "viaje",
        "confirmado_por",
    ]

    readonly_fields = [
        "fecha_registro",
        "fecha_actualizacion",
    ]

    ordering = [
        "-fecha_registro",
    ]