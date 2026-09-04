"""Servicios de búsqueda con Google Places."""

from math import (
    asin,
    cos,
    radians,
    sin,
    sqrt,
)

import requests
from django.conf import settings
from django.core.exceptions import (
    ValidationError,
)


GOOGLE_PLACES_URL = (
    "https://places.googleapis.com/"
    "v1/places:searchText"
)


def _distancia_km(
    origen_latitud,
    origen_longitud,
    destino_latitud,
    destino_longitud,
):
    origen_latitud = float(
        origen_latitud
    )

    origen_longitud = float(
        origen_longitud
    )

    destino_latitud = float(
        destino_latitud
    )

    destino_longitud = float(
        destino_longitud
    )

    radio_tierra_km = 6371.0

    diferencia_latitud = radians(
        destino_latitud
        - origen_latitud
    )

    diferencia_longitud = radians(
        destino_longitud
        - origen_longitud
    )

    valor = (
        sin(
            diferencia_latitud / 2
        ) ** 2
        + cos(
            radians(origen_latitud)
        )
        * cos(
            radians(destino_latitud)
        )
        * sin(
            diferencia_longitud / 2
        ) ** 2
    )

    angulo = 2 * asin(
        sqrt(valor)
    )

    return round(
        radio_tierra_km * angulo,
        2,
    )


def _mensaje_error_google(
    respuesta,
):
    try:
        contenido = respuesta.json()
    except ValueError:
        return None

    if not isinstance(
        contenido,
        dict,
    ):
        return None

    error = contenido.get(
        "error"
    )

    if not isinstance(
        error,
        dict,
    ):
        return None

    mensaje = error.get(
        "message"
    )

    if not mensaje:
        return None

    return str(mensaje)


def buscar_lugares_google(
    *,
    consulta,
    origen_latitud,
    origen_longitud,
    radio_metros=50000,
):
    api_key = getattr(
        settings,
        "GOOGLE_MAPS_PLACES_API_KEY",
        "",
    )

    if not api_key:
        raise ValidationError(
            "La búsqueda de lugares no "
            "está configurada."
        )

    origen_latitud_float = float(
        origen_latitud
    )

    origen_longitud_float = float(
        origen_longitud
    )

    payload = {
        "textQuery": consulta,
        "languageCode": "es",
        "regionCode": "NI",
        "pageSize": 10,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": (
                        origen_latitud_float
                    ),
                    "longitude": (
                        origen_longitud_float
                    ),
                },
                "radius": float(
                    radio_metros
                ),
            },
        },
    }

    headers = {
        "Content-Type": (
            "application/json"
        ),
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location"
        ),
    }

    try:
        respuesta = requests.post(
            GOOGLE_PLACES_URL,
            json=payload,
            headers=headers,
            timeout=12,
        )
    except requests.Timeout:
        raise ValidationError(
            "Google Places tardó demasiado "
            "en responder."
        )
    except requests.RequestException:
        raise ValidationError(
            "No fue posible conectar con "
            "Google Places."
        )

    if respuesta.status_code in [
        401,
        403,
    ]:
        raise ValidationError(
            "Google Places rechazó la clave. "
            "Verifica que Places API (New) "
            "esté habilitada y que la clave "
            "permita solicitudes desde "
            "el backend."
        )

    if not respuesta.ok:
        mensaje_google = (
            _mensaje_error_google(
                respuesta
            )
        )

        raise ValidationError(
            mensaje_google
            or (
                "Google Places no pudo "
                "procesar la búsqueda."
            )
        )

    try:
        contenido = respuesta.json()
    except ValueError:
        raise ValidationError(
            "Google Places devolvió una "
            "respuesta inválida."
        )

    lugares_google = contenido.get(
        "places",
        [],
    )

    resultados = []

    for lugar in lugares_google:
        if not isinstance(
            lugar,
            dict,
        ):
            continue

        ubicacion = lugar.get(
            "location"
        )

        if not isinstance(
            ubicacion,
            dict,
        ):
            continue

        latitud = ubicacion.get(
            "latitude"
        )

        longitud = ubicacion.get(
            "longitude"
        )

        if (
            latitud is None
            or longitud is None
        ):
            continue

        nombre_elemento = lugar.get(
            "displayName",
            {},
        )

        if isinstance(
            nombre_elemento,
            dict,
        ):
            nombre = nombre_elemento.get(
                "text",
                "",
            )
        else:
            nombre = str(
                nombre_elemento or ""
            )

        direccion = lugar.get(
            "formattedAddress",
            "",
        )

        distancia = _distancia_km(
            origen_latitud=(
                origen_latitud
            ),
            origen_longitud=(
                origen_longitud
            ),
            destino_latitud=latitud,
            destino_longitud=longitud,
        )

        resultados.append(
            {
                "place_id": lugar.get(
                    "id",
                    "",
                ),
                "nombre": (
                    nombre
                    or direccion
                    or consulta
                ),
                "direccion": (
                    direccion
                    or nombre
                    or consulta
                ),
                "latitud": round(
                    float(latitud),
                    7,
                ),
                "longitud": round(
                    float(longitud),
                    7,
                ),
                "distancia_km": (
                    distancia
                ),
            }
        )

    resultados.sort(
        key=lambda elemento: (
            elemento["distancia_km"]
        )
    )

    return resultados