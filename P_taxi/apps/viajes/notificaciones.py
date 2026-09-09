"""Notificaciones relacionadas con viajes."""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import ( # pyright: ignore[reportMissingModuleSource]
    close_old_connections,
    transaction, # pyright: ignore[reportMissingModuleSource]
)

from App_taxi.models import Conductor
from App_taxi.notification_services import (
    enviar_notificacion_usuario,
)

from .models import Viaje


logger = logging.getLogger(__name__)

_notification_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="notificaciones_viajes",
)


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


def _construir_nombre_pasajero(viaje):
    usuario = viaje.pasajero.usuario

    nombre = " ".join(
        parte.strip()
        for parte in [
            usuario.first_name or "",
            usuario.last_name or "",
        ]
        if parte and parte.strip()
    )

    return nombre or "Un pasajero"


def _construir_mensaje_nuevo_viaje(viaje):
    nombre_pasajero = (
        _construir_nombre_pasajero(viaje)
    )

    origen = str(
        viaje.origen_direccion or ""
    ).strip()

    destino = str(
        viaje.destino_direccion or ""
    ).strip()

    if not origen:
        origen = "Ubicación indicada en el mapa"

    if not destino:
        destino = "Sin destino especificado"

    cantidad = max(
        int(viaje.cantidad_pasajeros or 1),
        1,
    )

    texto_pasajeros = (
        "1 pasajero"
        if cantidad == 1
        else f"{cantidad} pasajeros"
    )

    mensaje = (
        f"{nombre_pasajero} solicita un "
        f"{viaje.tipo_vehiculo.nombre} para "
        f"{texto_pasajeros}. "
        f"Recoger en: {origen}. "
        f"Destino: {destino}."
    )

    if viaje.tarifa_acordada is not None:
        mensaje += (
            " Tarifa: C$ "
            f"{viaje.tarifa_acordada}."
        )

    return mensaje


def _enviar_nuevo_viaje_a_conductores(
    viaje_id,
):
    """
    Envía el nuevo viaje a conductores con el tipo
    de vehículo solicitado.

    No exige que el conductor tenga en_linea=True.
    Solamente requiere conductor, usuario, vehículo
    y notificaciones activas.
    """
    close_old_connections()

    try:
        viaje = (
            Viaje.objects
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "tipo_vehiculo",
            )
            .filter(
                pk=viaje_id,
                estado="buscando_conductor",
            )
            .first()
        )

        if not viaje:
            return 0

        conductores = (
            Conductor.objects
            .select_related("usuario")
            .filter(
                activo=True,
                estado_verificacion="aprobado",
                usuario__isnull=False,
                usuario__is_active=True,
                usuario__dispositivos_notificacion__activo=True,
                asignaciones__activa=True,
                asignaciones__vehiculo__estado_verificacion="aprobado",
                asignaciones__vehiculo__tipo_vehiculo=(
                    viaje.tipo_vehiculo
                ),
            )
            .distinct()
        )

        titulo = (
            "Nueva solicitud de "
            f"{viaje.tipo_vehiculo.nombre}"
        )

        mensaje = (
            _construir_mensaje_nuevo_viaje(viaje)
        )

        enviados = 0

        for conductor in conductores.iterator():
            if not conductor.usuario_id:
                continue

            enviados += _enviar_notificacion_segura(
                usuario=conductor.usuario,
                titulo=titulo,
                mensaje=mensaje,
                url=f"/viajes/{viaje.id}",
                tag=f"nuevo_viaje_{viaje.id}",
                datos={
                    "tipo": "nuevo_viaje_disponible",
                    "viaje_id": viaje.id,
                    "tipo_vehiculo_id": (
                        viaje.tipo_vehiculo_id
                    ),
                    "tipo_vehiculo_codigo": (
                        viaje.tipo_vehiculo.codigo
                    ),
                    "cantidad_pasajeros": (
                        viaje.cantidad_pasajeros
                    ),
                },
            )

        logger.info(
            "Viaje %s notificado a %s dispositivo(s).",
            viaje.id,
            enviados,
        )

        return enviados

    except Exception:
        logger.exception(
            "No fue posible notificar el nuevo viaje %s.",
            viaje_id,
        )

        return 0

    finally:
        close_old_connections()


def programar_notificacion_nuevo_viaje(
    *,
    viaje_id,
):
    """
    Inicia el envío después de confirmar la transacción,
    sin retrasar la respuesta al pasajero.
    """

    def iniciar_envio():
        _notification_executor.submit(
            _enviar_nuevo_viaje_a_conductores,
            viaje_id,
        )

    transaction.on_commit(iniciar_envio)
