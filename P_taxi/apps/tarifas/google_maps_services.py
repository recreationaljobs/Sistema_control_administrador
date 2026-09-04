"""Servicios de integración con Google Maps."""

import json
import math
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings
from django.core.exceptions import (
    ValidationError,
)


GOOGLE_ROUTES_URL = (
    "https://routes.googleapis.com/"
    "directions/v2:computeRoutes"
)

DOS_DECIMALES = Decimal("0.01")


def _convertir_duracion_a_minutos(
    duracion,
):
    valor = str(duracion or "").strip()

    if not valor.endswith("s"):
        raise ValidationError(
            "Google no devolvió una duración válida."
        )

    try:
        segundos = float(
            valor.removesuffix("s")
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValidationError(
            "Google no devolvió una duración válida."
        ) from error

    return max(
        1,
        math.ceil(segundos / 60),
    )


def _obtener_mensaje_error(datos):
    if not isinstance(datos, dict):
        return None

    error = datos.get("error")

    if not isinstance(error, dict):
        return None

    mensaje = error.get("message")

    if mensaje:
        return str(mensaje)

    return None


def calcular_ruta_google(
    *,
    origen_latitud,
    origen_longitud,
    destino_latitud,
    destino_longitud,
):
    api_key = getattr(
        settings,
        "GOOGLE_MAPS_ROUTES_API_KEY",
        "",
    )

    if not api_key:
        raise ValidationError(
            "No se configuró la clave de "
            "Google Routes API."
        )

    cuerpo = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(
                        origen_latitud
                    ),
                    "longitude": float(
                        origen_longitud
                    ),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(
                        destino_latitud
                    ),
                    "longitude": float(
                        destino_longitud
                    ),
                }
            }
        },
        "travelMode": "DRIVE",
        "computeAlternativeRoutes": False,
        "languageCode": "es-419",
        "units": "METRIC",
    }

    solicitud = urllib_request.Request(
        GOOGLE_ROUTES_URL,
        data=json.dumps(
            cuerpo
        ).encode("utf-8"),
        headers={
            "Content-Type": (
                "application/json"
            ),
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "routes.distanceMeters,"
                "routes.duration,"
                "routes.polyline."
                "encodedPolyline"
            ),
        },
        method="POST",
    )

    timeout = getattr(
        settings,
        "GOOGLE_MAPS_REQUEST_TIMEOUT",
        15,
    )

    try:
        with urllib_request.urlopen(
            solicitud,
            timeout=timeout,
        ) as respuesta:
            datos = json.loads(
                respuesta
                .read()
                .decode("utf-8")
            )

    except urllib_error.HTTPError as error:
        try:
            contenido = (
                error
                .read()
                .decode("utf-8")
            )

            datos_error = json.loads(
                contenido
            )

            mensaje_google = (
                _obtener_mensaje_error(
                    datos_error
                )
            )
        except Exception:
            mensaje_google = None

        mensaje = (
            mensaje_google
            or (
                "Google Routes rechazó "
                "la solicitud."
            )
        )

        raise ValidationError(
            mensaje
        ) from error

    except urllib_error.URLError as error:
        raise ValidationError(
            "No fue posible conectar con "
            "Google Routes."
        ) from error

    except TimeoutError as error:
        raise ValidationError(
            "Google Routes tardó demasiado "
            "en responder."
        ) from error

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as error:
        raise ValidationError(
            "Google Routes devolvió una "
            "respuesta inválida."
        ) from error

    rutas = datos.get("routes", [])

    if not rutas:
        raise ValidationError(
            "Google no encontró una ruta "
            "entre el origen y el destino."
        )

    ruta = rutas[0]

    distancia_metros = ruta.get(
        "distanceMeters"
    )

    duracion = ruta.get(
        "duration"
    )

    polyline_data = ruta.get(
        "polyline",
        {},
    )

    polyline = polyline_data.get(
        "encodedPolyline",
        "",
    )

    if distancia_metros is None:
        raise ValidationError(
            "Google no devolvió la distancia "
            "de la ruta."
        )

    distancia_km = (
        Decimal(
            str(distancia_metros)
        )
        / Decimal("1000")
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    duracion_minutos = (
        _convertir_duracion_a_minutos(
            duracion
        )
    )

    return {
        "distancia_metros": int(
            distancia_metros
        ),
        "distancia_km": distancia_km,
        "duracion_minutos": (
            duracion_minutos
        ),
        "polyline": polyline,
        "fuente": "google_routes",
    }