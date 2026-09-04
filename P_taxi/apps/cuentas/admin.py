"""Administración de cuentas móviles."""
from django.contrib import admin
from django.utils import timezone

from .models import (
    InvitacionConductor,
    VinculacionConductor,
)


@admin.register(InvitacionConductor)
class InvitacionConductorAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "conductor",
        "token",
        "activa",
        "mostrar_estado",
        "fecha_creacion",
        "fecha_vencimiento",
        "creado_por",
    )

    list_filter = (
        "activa",
        "fecha_creacion",
        "fecha_vencimiento",
    )

    search_fields = (
        "conductor__nombre",
        "conductor__apellido",
        "conductor__cedula",
        "conductor__telefono",
        "token",
    )

    readonly_fields = (
        "token",
        "fecha_creacion",
        "fecha_utilizacion",
        "creado_por",
    )

    autocomplete_fields = (
        "conductor",
    )

    fieldsets = (
        (
            "Conductor",
            {
                "fields": (
                    "conductor",
                )
            },
        ),
        (
            "Código de activación",
            {
                "fields": (
                    "token",
                    "activa",
                    "fecha_vencimiento",
                    "fecha_utilizacion",
                )
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "creado_por",
                    "fecha_creacion",
                )
            },
        ),
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.creado_por_id:
            obj.creado_por = request.user

        if not change:
            InvitacionConductor.objects.filter(
                conductor=obj.conductor,
                activa=True,
                fecha_utilizacion__isnull=True,
            ).update(
                activa=False
            )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.display(
        description="Estado"
    )
    def mostrar_estado(self, obj):
        if obj.fecha_utilizacion:
            return "Utilizada"

        if not obj.activa:
            return "Desactivada"

        if (
            timezone.now()
            >= obj.fecha_vencimiento
        ):
            return "Vencida"

        return "Disponible"

@admin.register(VinculacionConductor)
class VinculacionConductorAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "conductor",
        "sucursal",
        "tipo_vinculacion",
        "estado",
        "fecha_inicio",
        "fecha_fin",
    )

    search_fields = (
        "conductor__nombre",
        "conductor__apellido",
        "conductor__cedula",
        "sucursal__nombre",
    )

    list_filter = (
        "estado",
        "tipo_vinculacion",
        "sucursal",
    )

    raw_id_fields = (
        "conductor",
        "creado_por",
        "finalizado_por",
    )

    readonly_fields = (
        "fecha_fin",
        "finalizado_por",
    )