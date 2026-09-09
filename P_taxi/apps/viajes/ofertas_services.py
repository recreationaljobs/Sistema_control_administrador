"""Servicios para negociar ofertas de viajes."""

from datetime import timedelta
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from django.core.exceptions import ( # type: ignore
    ValidationError,
)
from django.db import transaction # pyright: ignore[reportMissingModuleSource]
from django.utils import timezone # pyright: ignore[reportMissingModuleSource]
from .services import aceptar_viaje

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
)
from apps.seguimiento.services import (
    validar_conductor_disponible,
)

from .models import (
    OfertaViaje,
    Viaje,
)
from .notificaciones import (
    programar_notificacion_viaje,
)


DOS_DECIMALES = Decimal("0.01")
SEGUNDOS_VIGENCIA_OFERTA = 25


@transaction.atomic
def crear_contraoferta(
    viaje_id,
    conductor,
    monto_propuesto,
    mensaje="",
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .get(pk=conductor.pk)
    )

    validar_conductor_disponible(
        conductor=conductor
    )

    asignacion = (
        AsignacionVehiculo.objects
        .select_for_update()
        .select_related(
            "vehiculo",
            "vehiculo__tipo_vehiculo",
        )
        .filter(
            conductor=conductor,
            activa=True,
        )
        .first()
    )

    if not asignacion:
        raise ValidationError(
            "No tienes un vehículo "
            "activo asignado."
        )

    vehiculo = asignacion.vehiculo

    if (
        vehiculo.estado_verificacion
        != "aprobado"
    ):
        raise ValidationError(
            "El vehículo no está aprobado."
        )

    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                "tipo_vehiculo",
                "pasajero",
            )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje solicitado no existe."
        )

    if viaje.estado != "buscando_conductor":
        raise ValidationError(
            "El viaje ya no recibe ofertas."
        )

    if (
        viaje.tipo_vehiculo_id
        != vehiculo.tipo_vehiculo_id
    ):
        raise ValidationError(
            "Tu vehículo no coincide con "
            "el tipo solicitado."
        )

    if viaje.tarifa_estimada is None:
        raise ValidationError(
            "El viaje no tiene una tarifa "
            "estimada calculada."
        )

    ahora = timezone.now()

    (
        OfertaViaje.objects
        .filter(
            viaje=viaje,
            conductor=conductor,
            estado="pendiente",
            fecha_vencimiento__lte=ahora,
        )
        .update(
            estado="vencida",
            fecha_respuesta=ahora,
        )
    )

    oferta_pendiente = (
        OfertaViaje.objects
        .filter(
            viaje=viaje,
            conductor=conductor,
            estado="pendiente",
            fecha_vencimiento__gt=ahora,
        )
        .exists()
    )

    if oferta_pendiente:
        raise ValidationError(
            "Ya tienes una contraoferta "
            "pendiente para este viaje."
        )

    monto = Decimal(
        str(monto_propuesto)
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    tarifa_base = (
        viaje.tarifa_acordada
        if viaje.tarifa_acordada is not None
        else viaje.tarifa_estimada
    )

    tarifa_original = Decimal(
        str(tarifa_base)
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    if monto <= Decimal("0"):
        raise ValidationError(
            "La contraoferta debe ser mayor que C$ 0.00."
        )

    oferta = OfertaViaje.objects.create(
        viaje=viaje,
        conductor=conductor,
        tarifa_original=tarifa_original,
        monto_propuesto=monto,
        mensaje=str(mensaje).strip(),
        estado="pendiente",
        fecha_vencimiento=(
            ahora
            + timedelta(
                seconds=(
                    SEGUNDOS_VIGENCIA_OFERTA
                )
            )
        ),
    )

    programar_notificacion_viaje(
        usuario=viaje.pasajero.usuario,
        titulo="Nueva contraoferta",
        mensaje=(
            "Un conductor propuso una tarifa "
            f"de C$ {oferta.monto_propuesto}."
        ),
        tipo="contraoferta_nueva",
        viaje_id=viaje.id,
        oferta_id=oferta.id,
    )

    return oferta

def actualizar_ofertas_vencidas(
    viaje=None,
):
    ahora = timezone.now()

    ofertas = OfertaViaje.objects.filter(
        estado="pendiente",
        fecha_vencimiento__lte=ahora,
    )

    if viaje:
        ofertas = ofertas.filter(
            viaje=viaje
        )

    return ofertas.update(
        estado="vencida",
        fecha_respuesta=ahora,
    )


@transaction.atomic
def aceptar_contraoferta(
    oferta_id,
    pasajero,
    usuario,
):
    try:
        oferta = (
            OfertaViaje.objects
            .select_for_update()
            .select_related(
                "viaje",
                "conductor",
                "conductor__usuario",
            )
            .get(pk=oferta_id)
        )
    except OfertaViaje.DoesNotExist:
        raise ValidationError(
            "La contraoferta no existe."
        )

    if (
        oferta.viaje.pasajero_id
        != pasajero.id
    ):
        raise ValidationError(
            "La contraoferta no pertenece "
            "a uno de tus viajes."
        )

    ahora = timezone.now()

    if (
        oferta.estado == "pendiente"
        and oferta.fecha_vencimiento <= ahora
    ):
        oferta.estado = "vencida"
        oferta.fecha_respuesta = ahora

        oferta.save(
            update_fields=[
                "estado",
                "fecha_respuesta",
                "fecha_actualizacion",
            ]
        )

        raise ValidationError(
            "La contraoferta ya venció."
        )

    if oferta.estado != "pendiente":
        raise ValidationError(
            "La contraoferta ya fue respondida."
        )

    if (
        oferta.viaje.estado
        != "buscando_conductor"
    ):
        raise ValidationError(
            "El viaje ya no está buscando "
            "conductor."
        )

    viaje = aceptar_viaje(
        viaje_id=oferta.viaje_id,
        conductor=oferta.conductor,
        usuario=usuario,
        validar_disponibilidad=False,
    )

    viaje.tarifa_acordada = (
        oferta.monto_propuesto
    )

    viaje.save(
        update_fields=[
            "tarifa_acordada",
            "fecha_actualizacion",
        ]
    )

    oferta.estado = "aceptada"
    oferta.fecha_respuesta = ahora

    oferta.save(
        update_fields=[
            "estado",
            "fecha_respuesta",
            "fecha_actualizacion",
        ]
    )

    (
        OfertaViaje.objects
        .filter(
            viaje_id=viaje.id,
            estado="pendiente",
        )
        .exclude(pk=oferta.pk)
        .update(
            estado="rechazada",
            fecha_respuesta=ahora,
        )
    )

    if oferta.conductor.usuario:
        programar_notificacion_viaje(
            usuario=oferta.conductor.usuario,
            titulo="Contraoferta aceptada",
            mensaje=(
                "El pasajero aceptó tu propuesta "
                f"de C$ {oferta.monto_propuesto}."
            ),
            tipo="contraoferta_aceptada",
            viaje_id=viaje.id,
            oferta_id=oferta.id,
        )

    return oferta, viaje


@transaction.atomic
def rechazar_contraoferta(
    oferta_id,
    pasajero,
):
    try:
        oferta = (
            OfertaViaje.objects
            .select_for_update()
            .select_related("viaje")
            .get(pk=oferta_id)
        )
    except OfertaViaje.DoesNotExist:
        raise ValidationError(
            "La contraoferta no existe."
        )

    if (
        oferta.viaje.pasajero_id
        != pasajero.id
    ):
        raise ValidationError(
            "La contraoferta no pertenece "
            "a uno de tus viajes."
        )

    ahora = timezone.now()

    if (
        oferta.estado == "pendiente"
        and oferta.fecha_vencimiento <= ahora
    ):
        oferta.estado = "vencida"
        oferta.fecha_respuesta = ahora

        oferta.save(
            update_fields=[
                "estado",
                "fecha_respuesta",
                "fecha_actualizacion",
            ]
        )

        raise ValidationError(
            "La contraoferta ya venció."
        )

    if oferta.estado != "pendiente":
        raise ValidationError(
            "La contraoferta ya fue respondida."
        )

    oferta.estado = "rechazada"
    oferta.fecha_respuesta = ahora

    oferta.save(
        update_fields=[
            "estado",
            "fecha_respuesta",
            "fecha_actualizacion",
        ]
    )
    if oferta.conductor.usuario:
        programar_notificacion_viaje(
            usuario=oferta.conductor.usuario,
            titulo="Contraoferta rechazada",
            mensaje=(
                "El pasajero rechazó tu "
                "contraoferta."
            ),
            tipo="contraoferta_rechazada",
            viaje_id=oferta.viaje_id,
            oferta_id=oferta.id,
        )

    return oferta

@transaction.atomic
def cancelar_contraoferta_conductor(
    oferta_id,
    conductor,
):
    try:
        oferta = (
            OfertaViaje.objects
            .select_for_update()
            .select_related(
                "viaje",
                "viaje__pasajero",
                "viaje__pasajero__usuario",
            )
            .get(pk=oferta_id)
        )
    except OfertaViaje.DoesNotExist:
        raise ValidationError(
            "La contraoferta no existe."
        )

    if oferta.conductor_id != conductor.id:
        raise ValidationError(
            "La contraoferta no pertenece "
            "al conductor autenticado."
        )

    ahora = timezone.now()

    if (
        oferta.estado == "pendiente"
        and oferta.fecha_vencimiento <= ahora
    ):
        oferta.estado = "vencida"
        oferta.fecha_respuesta = ahora

        oferta.save(
            update_fields=[
                "estado",
                "fecha_respuesta",
                "fecha_actualizacion",
            ]
        )

        raise ValidationError(
            "La contraoferta ya venció."
        )

    if oferta.estado != "pendiente":
        raise ValidationError(
            "Solamente puedes retirar una "
            "contraoferta pendiente."
        )

    oferta.estado = "cancelada"
    oferta.fecha_respuesta = ahora

    oferta.save(
        update_fields=[
            "estado",
            "fecha_respuesta",
            "fecha_actualizacion",
        ]
    )
    programar_notificacion_viaje(
        usuario=oferta.viaje.pasajero.usuario,
        titulo="Contraoferta retirada",
        mensaje=(
            "El conductor retiró su "
            "contraoferta."
        ),
        tipo="contraoferta_cancelada",
        viaje_id=oferta.viaje_id,
        oferta_id=oferta.id,
    )

    return oferta
