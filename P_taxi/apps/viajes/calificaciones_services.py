"""Servicios de calificaciones de viajes."""

from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction

from App_taxi.models import Conductor
from apps.pasajeros.models import Pasajero

from .models import (
    CalificacionViaje,
    Viaje,
)


@transaction.atomic
def calificar_viaje(
    *,
    viaje_id,
    usuario,
    puntuacion,
    comentario="",
):
    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "conductor",
                "conductor__usuario",
            )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje solicitado no existe."
        )

    if viaje.estado != "completado":
        raise ValidationError(
            "Solamente se pueden calificar "
            "viajes completados."
        )

    if not viaje.conductor_id:
        raise ValidationError(
            "El viaje no tiene un conductor."
        )

    pasajero = (
        Pasajero.objects
        .filter(usuario=usuario)
        .first()
    )

    conductor = (
        Conductor.objects
        .filter(usuario=usuario)
        .first()
    )

    if (
        pasajero
        and viaje.pasajero_id
        == pasajero.id
    ):
        tipo = (
            CalificacionViaje
            .PASAJERO_A_CONDUCTOR
        )

        usuario_evaluado = (
            viaje.conductor.usuario
        )

    elif (
        conductor
        and viaje.conductor_id
        == conductor.id
    ):
        tipo = (
            CalificacionViaje
            .CONDUCTOR_A_PASAJERO
        )

        usuario_evaluado = (
            viaje.pasajero.usuario
        )

    else:
        raise ValidationError(
            "No tienes permiso para calificar "
            "este viaje."
        )

    if not usuario_evaluado:
        raise ValidationError(
            "El usuario que deseas calificar "
            "no tiene una cuenta activa."
        )

    ya_califico = (
        CalificacionViaje.objects
        .filter(
            viaje=viaje,
            tipo=tipo,
        )
        .exists()
    )

    if ya_califico:
        raise ValidationError(
            "Ya realizaste la calificación "
            "correspondiente a este viaje."
        )

    calificacion = (
        CalificacionViaje.objects.create(
            viaje=viaje,
            tipo=tipo,
            usuario_evaluador=usuario,
            usuario_evaluado=(
                usuario_evaluado
            ),
            puntuacion=puntuacion,
            comentario=(
                str(comentario).strip()
            ),
        )
    )

    return calificacion