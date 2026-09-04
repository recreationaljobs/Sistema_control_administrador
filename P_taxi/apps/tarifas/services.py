"""Cálculo de precios y comisiones."""

import logging
import math
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from django.core.exceptions import (
    ValidationError,
)
from django.db.models import Q
from django.utils import timezone

from .google_maps_services import (
    calcular_ruta_google,
)
from .models import TarifaVehiculo


logger = logging.getLogger(__name__)

DOS_DECIMALES = Decimal("0.01")


def calcular_distancia_haversine(
    origen_latitud,
    origen_longitud,
    destino_latitud,
    destino_longitud,
):
    latitud_1 = math.radians(
        float(origen_latitud)
    )

    longitud_1 = math.radians(
        float(origen_longitud)
    )

    latitud_2 = math.radians(
        float(destino_latitud)
    )

    longitud_2 = math.radians(
        float(destino_longitud)
    )

    diferencia_latitud = (
        latitud_2 - latitud_1
    )

    diferencia_longitud = (
        longitud_2 - longitud_1
    )

    calculo = (
        math.sin(
            diferencia_latitud / 2
        ) ** 2
        + math.cos(latitud_1)
        * math.cos(latitud_2)
        * math.sin(
            diferencia_longitud / 2
        ) ** 2
    )

    angulo = 2 * math.atan2(
        math.sqrt(calculo),
        math.sqrt(1 - calculo),
    )

    radio_tierra_km = 6371.0088

    return Decimal(
        str(
            radio_tierra_km * angulo
        )
    )


def obtener_tarifa_vigente(
    tipo_vehiculo,
    sucursal=None,
):
    ahora = timezone.now()

    tarifas = (
        TarifaVehiculo.objects
        .select_related(
            "tipo_vehiculo",
            "sucursal",
        )
        .filter(
            tipo_vehiculo=tipo_vehiculo,
            activo=True,
            vigencia_desde__lte=ahora,
        )
        .filter(
            Q(vigencia_hasta__isnull=True)
            | Q(vigencia_hasta__gt=ahora)
        )
    )

    tarifa = None

    if sucursal:
        tarifa = (
            tarifas
            .filter(
                sucursal=sucursal
            )
            .order_by(
                "-vigencia_desde"
            )
            .first()
        )

    if not tarifa:
        tarifa = (
            tarifas
            .filter(
                sucursal__isnull=True
            )
            .order_by(
                "-vigencia_desde"
            )
            .first()
        )

    if not tarifa:
        raise ValidationError(
            "No existe una tarifa activa "
            "para el tipo de vehículo."
        )

    return tarifa


def calcular_tarifa_estimada(
    tipo_vehiculo,
    origen_latitud,
    origen_longitud,
    destino_latitud,
    destino_longitud,
    sucursal=None,
):
    tarifa = obtener_tarifa_vigente(
        tipo_vehiculo=tipo_vehiculo,
        sucursal=sucursal,
    )

    distancia_lineal = (
        calcular_distancia_haversine(
            origen_latitud=origen_latitud,
            origen_longitud=origen_longitud,
            destino_latitud=destino_latitud,
            destino_longitud=destino_longitud,
        )
    )

    polyline = ""
    fuente_ruta = "estimacion_local"

    try:
        ruta_google = (
            calcular_ruta_google(
                origen_latitud=(
                    origen_latitud
                ),
                origen_longitud=(
                    origen_longitud
                ),
                destino_latitud=(
                    destino_latitud
                ),
                destino_longitud=(
                    destino_longitud
                ),
            )
        )

        distancia_estimada = (
            ruta_google[
                "distancia_km"
            ]
        )

        duracion_estimada_minutos = (
            ruta_google[
                "duracion_minutos"
            ]
        )

        polyline = ruta_google[
            "polyline"
        ]

        fuente_ruta = ruta_google[
            "fuente"
        ]

    except ValidationError as error:
        logger.warning(
            "No fue posible calcular la "
            "ruta con Google. Se utilizará "
            "la estimación local: %s",
            "; ".join(error.messages),
        )

        distancia_estimada = (
            distancia_lineal
            * tarifa
            .factor_distancia_ruta
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

        velocidades_promedio = {
            "taxi": Decimal("25"),
            "mototaxi": Decimal("20"),
            "moto": Decimal("30"),
        }

        velocidad_promedio = (
            velocidades_promedio.get(
                tipo_vehiculo.codigo,
                Decimal("25"),
            )
        )

        duracion_estimada_minutos = max(
            1,
            math.ceil(
                float(
                    (
                        distancia_estimada
                        / velocidad_promedio
                    )
                    * Decimal("60")
                )
            ),
        )

    subtotal = (
        tarifa.tarifa_base
        + (
            distancia_estimada
            * tarifa.precio_por_km
        )
    )

    total = max(
        subtotal,
        tarifa.tarifa_minima,
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    comision_plataforma = (
        total
        * tarifa
        .porcentaje_comision_plataforma
        / Decimal("100")
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    ganancia_conductor = (
        total - comision_plataforma
    ).quantize(
        DOS_DECIMALES,
        rounding=ROUND_HALF_UP,
    )

    return {
        "tarifa_id": tarifa.id,
        "moneda": tarifa.moneda,
        "distancia_lineal_km": (
            distancia_lineal.quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )
        ),
        "distancia_estimada_km": (
            distancia_estimada
        ),
        "duracion_estimada_minutos": (
            duracion_estimada_minutos
        ),
        "tarifa_base": (
            tarifa.tarifa_base
        ),
        "precio_por_km": (
            tarifa.precio_por_km
        ),
        "tarifa_minima": (
            tarifa.tarifa_minima
        ),
        "tarifa_estimada": total,
        "porcentaje_comision": (
            tarifa
            .porcentaje_comision_plataforma
        ),
        "comision_estimada": (
            comision_plataforma
        ),
        "ganancia_estimada_conductor": (
            ganancia_conductor
        ),
        "polyline": polyline,
        "fuente_ruta": fuente_ruta,
    }