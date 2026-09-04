"""Notificaciones relacionadas con viajes."""

import logging

from django.db import transaction

from App_taxi.notification_services import (
    enviar_notificacion_usuario,
)


logger = logging.getLogger(__name__)


def _enviar_notificacion_segura(
    *,
    usuario,
    titulo,
    mensaje,
    url,
    tag,
    datos,
):
    try:
        return enviar_notificacion_usuario(
            usuario=usuario,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
            tag=tag,
            datos=datos,
        )
    except Exception:
        logger.exception(
            "No se pudo enviar una notificación "
            "del módulo de viajes al usuario %s.",
            usuario.id,
        )

        return 0


def programar_notificacion_viaje(
    *,
    usuario,
    titulo,
    mensaje,
    tipo,
    viaje_id,
    oferta_id=None,
):
    datos = {
        "tipo": tipo,
        "viaje_id": viaje_id,
        "oferta_id": oferta_id,
    }

    url = f"/viajes/{viaje_id}"

    if oferta_id:
        url = (
            f"/viajes/{viaje_id}"
            f"/ofertas/{oferta_id}"
        )

    transaction.on_commit(
        lambda: _enviar_notificacion_segura(
            usuario=usuario,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
            tag=tipo,
            datos=datos,
        )
    )