"""Servicios de pagos de viajes."""

from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction
from django.utils import timezone

from App_taxi.models import Conductor
from .notificaciones import (
    programar_notificacion_viaje,
)

from .models import (
    PagoViaje,
)


@transaction.atomic
def confirmar_pago_efectivo(
    *,
    viaje_id,
    usuario,
):
    conductor = (
        Conductor.objects
        .filter(usuario=usuario)
        .first()
    )

    if not conductor:
        raise ValidationError(
            "La cuenta no tiene un perfil "
            "de conductor."
        )

    try:
        pago = (
            PagoViaje.objects
            .select_for_update()
            .select_related(
                    "viaje",
                    "viaje__conductor",
                    "viaje__pasajero",
                    "viaje__pasajero__usuario",
                )
            .get(viaje_id=viaje_id)
        )
    except PagoViaje.DoesNotExist:
        raise ValidationError(
            "El viaje no tiene un pago "
            "registrado."
        )

    viaje = pago.viaje

    if viaje.conductor_id != conductor.id:
        raise ValidationError(
            "El pago no pertenece a uno "
            "de tus viajes."
        )

    if viaje.estado != "completado":
        raise ValidationError(
            "El viaje todavía no está "
            "completado."
        )

    if (
        pago.metodo
        != PagoViaje.METODO_EFECTIVO
    ):
        raise ValidationError(
            "Este pago no corresponde "
            "al método efectivo."
        )

    if (
        pago.estado
        == PagoViaje.ESTADO_PAGADO
    ):
        return pago, False

    if (
        pago.estado
        != PagoViaje.ESTADO_PENDIENTE
    ):
        raise ValidationError(
            "El pago no se encuentra pendiente."
        )

    pago.estado = PagoViaje.ESTADO_PAGADO
    pago.confirmado_por = usuario
    pago.fecha_pago = timezone.now()

    pago.save(
        update_fields=[
            "estado",
            "confirmado_por",
            "fecha_pago",
            "fecha_actualizacion",
        ]
    )
    programar_notificacion_viaje(
        usuario=viaje.pasajero.usuario,
        titulo="Pago confirmado",
        mensaje=(
            "El conductor confirmó el pago "
            f"en efectivo de C$ {pago.monto}."
        ),
        tipo="pago_efectivo_confirmado",
        viaje_id=viaje.id,
    )

    return pago, True