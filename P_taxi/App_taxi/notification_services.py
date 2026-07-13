import logging
from pathlib import Path

import firebase_admin
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from firebase_admin import credentials, messaging

from App_taxi.models import DispositivoNotificacion


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