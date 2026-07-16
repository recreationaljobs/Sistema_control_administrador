import logging
from pathlib import Path

import firebase_admin
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from firebase_admin import credentials, messaging

from django.utils import timezone

from App_taxi.models import (
    AsignacionVehiculo,
    DispositivoNotificacion,
    RegistroNotificacionMantenimiento,
    Usuario,
)



logger = logging.getLogger(__name__)


def obtener_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    ruta_credenciales = getattr(
        settings,
        "FIREBASE_CREDENTIALS_PATH",
        "",
    )

    if not ruta_credenciales:
        raise ImproperlyConfigured(
            "No se configuró FIREBASE_CREDENTIALS_PATH."
        )

    archivo = Path(ruta_credenciales)

    if not archivo.is_file():
        raise ImproperlyConfigured(
            "No se encontró el archivo privado de Firebase."
        )

    credencial = credentials.Certificate(
        str(archivo)
    )

    return firebase_admin.initialize_app(
        credencial
    )


def enviar_notificacion_usuario(
    *,
    usuario,
    titulo,
    mensaje,
    url,
    tag,
):
    dispositivos = (
        DispositivoNotificacion.objects
        .filter(
            usuario=usuario,
            activo=True,
        )
    )

    if not dispositivos.exists():
        return 0

    firebase_app = obtener_firebase_app()

    enviados = 0

    for dispositivo in dispositivos:
        try:
            mensaje_firebase = messaging.Message(
                data={
                    "title": str(titulo),
                    "body": str(mensaje),
                    "url": str(url),
                    "tag": str(tag),
                },
                webpush=messaging.WebpushConfig(
                    headers={
                        "Urgency": "high",
                    },
                ),
                token=dispositivo.token,
            )

            messaging.send(
                mensaje_firebase,
                app=firebase_app,
            )

            enviados += 1

        except Exception as error:
            logger.exception(
                "No se pudo enviar la notificación "
                "al dispositivo %s del usuario %s.",
                dispositivo.id,
                usuario.id,
            )

            nombre_error = (
                error.__class__.__name__
            )

            if nombre_error in {
                "UnregisteredError",
                "SenderIdMismatchError",
            }:
                dispositivo.activo = False
                dispositivo.save(
                    update_fields=["activo"]
                )

    return enviados

def procesar_alerta_aceite_conductor(
    *,
    vehiculo,
    alerta,
):
    asignacion = (
        AsignacionVehiculo.objects
        .select_related(
            "conductor",
            "conductor__usuario",
            "conductor__sucursal",
            "vehiculo",
            "vehiculo__sucursal",
        )
        .filter(
            vehiculo=vehiculo,
            activa=True,
        )
        .first()
    )

    if not asignacion:
        logger.info(
            "El vehículo %s no tiene una "
            "asignación activa.",
            vehiculo.id,
        )

        return 0

    conductor = asignacion.conductor
    usuario = conductor.usuario

    if not conductor.activo:
        logger.info(
            "El conductor %s está inactivo.",
            conductor.id,
        )

        return 0

    if not usuario:
        logger.info(
            "El conductor %s no tiene "
            "usuario relacionado.",
            conductor.id,
        )

        return 0

    if not usuario.is_active:
        logger.info(
            "El usuario %s está inactivo.",
            usuario.id,
        )

        return 0

    # /*
    #  * El vehículo y el conductor deben
    #  * pertenecer al mismo entorno.
    #  *
    #  * Ambos sin sucursal:
    #  * grupo del superadministrador.
    #  *
    #  * Ambos con la misma sucursal:
    #  * grupo del administrador de sucursal.
    #  */
    if (
        conductor.sucursal_id
        != vehiculo.sucursal_id
    ):
        logger.warning(
            "No se envió la alerta porque "
            "el vehículo %s y el conductor %s "
            "pertenecen a entornos diferentes.",
            vehiculo.id,
            conductor.id,
        )

        return 0

    kilometraje_actual = int(
        alerta.get(
            "kilometraje_actual",
            vehiculo.kilometraje_actual or 0,
        )
    )

    kilometraje_objetivo = int(
        alerta.get(
            "proximo_km",
            0,
        )
    )

    faltan_km = int(
        alerta.get(
            "faltan_km",
            (
                kilometraje_objetivo
                - kilometraje_actual
            ),
        )
    )

    nombre_conductor = (
        f"{conductor.nombre} "
        f"{conductor.apellido}"
    ).strip()

    descripcion_vehiculo = (
        f"{vehiculo.marca} "
        f"{vehiculo.modelo}, "
        f"placa {vehiculo.placa}"
    ).strip()

    if faltan_km <= 0:
        tipo = (
            RegistroNotificacionMantenimiento
            .TIPO_ACEITE_VENCIDO
        )

        titulo = (
            "Cambio de aceite pendiente"
        )

        exceso_km = abs(faltan_km)

        if exceso_km > 0:
            mensaje = (
                f"Hola {nombre_conductor}, "
                f"debes realizar el cambio de "
                f"aceite del vehículo "
                f"{descripcion_vehiculo}. "
                f"El kilometraje programado de "
                f"{kilometraje_objetivo} km ya "
                f"fue superado por "
                f"{exceso_km} km."
            )
        else:
            mensaje = (
                f"Hola {nombre_conductor}, "
                f"debes realizar el cambio de "
                f"aceite del vehículo "
                f"{descripcion_vehiculo}. "
                f"Ya alcanzó el kilometraje "
                f"programado de "
                f"{kilometraje_objetivo} km."
            )

    else:
        tipo = (
            RegistroNotificacionMantenimiento
            .TIPO_ACEITE_PROXIMO
        )

        titulo = (
            "Próximo cambio de aceite"
        )

        mensaje = (
            f"Hola {nombre_conductor}, "
            f"al vehículo "
            f"{descripcion_vehiculo} "
            f"le faltan {faltan_km} km "
            f"para realizar el cambio "
            f"de aceite."
        )

    registro, creado = (
        RegistroNotificacionMantenimiento
        .objects
        .get_or_create(
            usuario=usuario,
            vehiculo=vehiculo,
            tipo=tipo,
            kilometraje_objetivo=(
                kilometraje_objetivo
            ),
            defaults={
                "kilometraje_detectado":
                    kilometraje_actual,

                "titulo":
                    titulo,

                "mensaje":
                    mensaje,
            },
        )
    )

    # /*
    #  * Si esta alerta ya fue enviada para
    #  * el mismo conductor, vehículo, tipo
    #  * y kilometraje objetivo, no se repite.
    #  */
    if registro.enviada:
        return 0

    campos_actualizados = []

    if (
        registro.kilometraje_detectado
        != kilometraje_actual
    ):
        registro.kilometraje_detectado = (
            kilometraje_actual
        )

        campos_actualizados.append(
            "kilometraje_detectado"
        )

    if registro.titulo != titulo:
        registro.titulo = titulo
        campos_actualizados.append(
            "titulo"
        )

    if registro.mensaje != mensaje:
        registro.mensaje = mensaje
        campos_actualizados.append(
            "mensaje"
        )

    if campos_actualizados:
        registro.save(
            update_fields=campos_actualizados
        )

    url = getattr(
        settings,
        "FRONTEND_MANTENIMIENTO_URL",
        "/mantenimiento",
    )

    enviados = enviar_notificacion_usuario(
        usuario=usuario,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        tag=(
            f"cambio-aceite-"
            f"{vehiculo.id}-"
            f"{usuario.id}-"
            f"{tipo.lower()}-"
            f"{kilometraje_objetivo}"
        ),
    )

    if enviados > 0:
        registro.enviada = True
        registro.fecha_envio = (
            timezone.now()
        )

        registro.save(
            update_fields=[
                "enviada",
                "fecha_envio",
            ]
        )

    return enviados



def procesar_alerta_aceite_administradores(
    *,
    vehiculo,
    alerta,
):
    if vehiculo.sucursal_id is None:
        administradores = (
            Usuario.objects
            .select_related(
                "rol",
                "sucursal",
            )
            .filter(
                is_active=True,
                sucursal__isnull=True,
                rol__codigo__in=[
                    "superadmin",
                    "super_admin",
                ],
            )
        )
    else:
        administradores = (
            Usuario.objects
            .select_related(
                "rol",
                "sucursal",
            )
            .filter(
                is_active=True,
                sucursal_id=vehiculo.sucursal_id,
                rol__codigo="admin_sucursal",
            )
        )

    asignacion = (
        AsignacionVehiculo.objects
        .filter(
            vehiculo=vehiculo,
            activa=True,
        )
        .select_related(
            "conductor",
        )
        .first()
    )

    if asignacion:
        nombre_conductor = (
            f"{asignacion.conductor.nombre} "
            f"{asignacion.conductor.apellido}"
        ).strip()
    else:
        nombre_conductor = (
            "sin conductor asignado"
        )

    kilometraje_actual = int(
        alerta.get(
            "kilometraje_actual",
            vehiculo.kilometraje_actual or 0,
        )
    )

    kilometraje_objetivo = int(
        alerta.get(
            "proximo_km",
            0,
        )
    )

    faltan_km = int(
        alerta.get(
            "faltan_km",
            kilometraje_objetivo
            - kilometraje_actual,
        )
    )

    descripcion_vehiculo = (
        f"{vehiculo.marca} "
        f"{vehiculo.modelo}, "
        f"placa {vehiculo.placa}"
    ).strip()

    if faltan_km <= 0:
        tipo = (
            RegistroNotificacionMantenimiento
            .TIPO_ACEITE_VENCIDO
        )

        titulo = (
            "Cambio de aceite pendiente"
        )

        exceso_km = abs(faltan_km)

        if exceso_km > 0:
            mensaje = (
                f"El vehículo "
                f"{descripcion_vehiculo}, "
                f"asignado a "
                f"{nombre_conductor}, "
                f"requiere cambio de aceite. "
                f"El kilometraje objetivo de "
                f"{kilometraje_objetivo} km "
                f"fue superado por "
                f"{exceso_km} km."
            )
        else:
            mensaje = (
                f"El vehículo "
                f"{descripcion_vehiculo}, "
                f"asignado a "
                f"{nombre_conductor}, "
                f"alcanzó el kilometraje "
                f"programado de "
                f"{kilometraje_objetivo} km "
                f"para realizar el cambio "
                f"de aceite."
            )

    else:
        tipo = (
            RegistroNotificacionMantenimiento
            .TIPO_ACEITE_PROXIMO
        )

        titulo = (
            "Próximo cambio de aceite"
        )

        mensaje = (
            f"El vehículo "
            f"{descripcion_vehiculo}, "
            f"asignado a "
            f"{nombre_conductor}, "
            f"está a {faltan_km} km "
            f"del próximo cambio "
            f"de aceite."
        )

    url = getattr(
        settings,
        "FRONTEND_MANTENIMIENTO_URL",
        "/mantenimiento",
    )

    total_enviados = 0

    for administrador in administradores:
        registro, _ = (
            RegistroNotificacionMantenimiento
            .objects
            .get_or_create(
                usuario=administrador,
                vehiculo=vehiculo,
                tipo=tipo,
                kilometraje_objetivo=(
                    kilometraje_objetivo
                ),
                defaults={
                    "kilometraje_detectado":
                        kilometraje_actual,
                    "titulo":
                        titulo,
                    "mensaje":
                        mensaje,
                },
            )
        )

        if registro.enviada:
            continue

        registro.kilometraje_detectado = (
            kilometraje_actual
        )
        registro.titulo = titulo
        registro.mensaje = mensaje

        registro.save(
            update_fields=[
                "kilometraje_detectado",
                "titulo",
                "mensaje",
            ]
        )

        enviados = enviar_notificacion_usuario(
            usuario=administrador,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
            tag=(
                f"aceite-admin-"
                f"{vehiculo.id}-"
                f"{administrador.id}-"
                f"{tipo.lower()}-"
                f"{kilometraje_objetivo}"
            ),
        )

        if enviados > 0:
            registro.enviada = True
            registro.fecha_envio = (
                timezone.now()
            )

            registro.save(
                update_fields=[
                    "enviada",
                    "fecha_envio",
                ]
            )

        total_enviados += enviados

    return total_enviados