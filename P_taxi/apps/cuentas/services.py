"""Servicios para cuentas y vinculaciones de conductores."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
    Sucursal,
)

from .models import VinculacionConductor


@transaction.atomic
def vincular_conductor_a_sucursal(
    conductor,
    sucursal,
    usuario=None,
    tipo_vinculacion="empleado",
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .select_related("usuario")
        .get(pk=conductor.pk)
    )

    sucursal = (
        Sucursal.objects
        .select_for_update()
        .get(pk=sucursal.pk)
    )

    if (
        conductor.estado_verificacion
        != "aprobado"
    ):
        raise ValidationError(
            "El conductor debe estar aprobado "
            "antes de vincularlo a una sucursal."
        )

    vinculacion_activa = (
        VinculacionConductor.objects
        .select_for_update()
        .filter(
            conductor=conductor,
            estado="activa",
        )
        .first()
    )

    if vinculacion_activa:
        if (
            vinculacion_activa.sucursal_id
            == sucursal.id
        ):
            return vinculacion_activa

        raise ValidationError(
            "El conductor ya pertenece a "
            "otra sucursal."
        )

    vinculacion = (
        VinculacionConductor.objects.create(
            conductor=conductor,
            sucursal=sucursal,
            tipo_vinculacion=tipo_vinculacion,
            estado="activa",
            creado_por=usuario,
        )
    )

    conductor.sucursal = sucursal

    conductor.save(
        update_fields=[
            "sucursal",
        ]
    )

    if conductor.usuario_id:
        conductor.usuario.sucursal = sucursal

        conductor.usuario.save(
            update_fields=[
                "sucursal",
            ]
        )

    return vinculacion


@transaction.atomic
def desvincular_conductor_de_sucursal(
    conductor,
    usuario=None,
    motivo="",
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .select_related(
            "usuario",
            "sucursal",
        )
        .get(pk=conductor.pk)
    )

    sucursal_anterior_id = (
        conductor.sucursal_id
    )

    vinculacion = (
        VinculacionConductor.objects
        .select_for_update()
        .filter(
            conductor=conductor,
            estado="activa",
        )
        .first()
    )

    if vinculacion:
        vinculacion.finalizar(
            usuario=usuario,
            motivo=motivo,
        )

    asignaciones = (
        AsignacionVehiculo.objects
        .select_for_update()
        .filter(
            conductor=conductor,
            activa=True,
        )
    )

    cantidad_asignaciones = (
        asignaciones.update(
            activa=False,
            fecha_fin=timezone.localdate(),
        )
    )

    conductor.sucursal = None

    conductor.save(
        update_fields=[
            "sucursal",
        ]
    )

    if (
        conductor.usuario_id
        and conductor.usuario.sucursal_id
        == sucursal_anterior_id
    ):
        conductor.usuario.sucursal = None

        conductor.usuario.save(
            update_fields=[
                "sucursal",
            ]
        )

    return (
        conductor,
        vinculacion,
        cantidad_asignaciones,
    )