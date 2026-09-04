"""Vistas de tarifas y lugares."""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tarifas.google_maps_services import (
    calcular_ruta_google,
)
from apps.tarifas.places_services import (
    buscar_lugares_google,
)
from apps.tarifas.services import (
    calcular_tarifa_estimada,
)

from .places_serializers import (
    BuscarLugarSerializer,
)
from .serializers import (
    CalcularRutaSerializer,
    EstimarTarifaSerializer,
)


class EstimarTarifaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = (
            EstimarTarifaSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        datos = serializer.validated_data

        tipo_vehiculo = datos[
            "tipo_vehiculo"
        ]

        try:
            estimacion = (
                calcular_tarifa_estimada(
                    tipo_vehiculo=(
                        tipo_vehiculo
                    ),
                    origen_latitud=datos[
                        "origen_latitud"
                    ],
                    origen_longitud=datos[
                        "origen_longitud"
                    ],
                    destino_latitud=datos[
                        "destino_latitud"
                    ],
                    destino_longitud=datos[
                        "destino_longitud"
                    ],
                    sucursal=None,
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "tipo_vehiculo": {
                    "id": (
                        tipo_vehiculo.id
                    ),
                    "codigo": (
                        tipo_vehiculo.codigo
                    ),
                    "nombre": (
                        tipo_vehiculo.nombre
                    ),
                },
                "moneda": estimacion[
                    "moneda"
                ],
                "distancia_lineal_km": (
                    estimacion[
                        "distancia_lineal_km"
                    ]
                ),
                "distancia_estimada_km": (
                    estimacion[
                        "distancia_estimada_km"
                    ]
                ),
                "duracion_estimada_minutos": (
                    estimacion[
                        "duracion_estimada_minutos"
                    ]
                ),
                "tarifa_base": estimacion[
                    "tarifa_base"
                ],
                "precio_por_km": estimacion[
                    "precio_por_km"
                ],
                "tarifa_minima": estimacion[
                    "tarifa_minima"
                ],
                "tarifa_estimada": estimacion[
                    "tarifa_estimada"
                ],
                "polyline": estimacion[
                    "polyline"
                ],
                "fuente_ruta": estimacion[
                    "fuente_ruta"
                ],
            },
            status=status.HTTP_200_OK,
        )


class CalcularRutaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = (
            CalcularRutaSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        datos = serializer.validated_data

        try:
            ruta = calcular_ruta_google(
                origen_latitud=datos[
                    "origen_latitud"
                ],
                origen_longitud=datos[
                    "origen_longitud"
                ],
                destino_latitud=datos[
                    "destino_latitud"
                ],
                destino_longitud=datos[
                    "destino_longitud"
                ],
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            ruta,
            status=status.HTTP_200_OK,
        )


class BuscarLugaresView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = BuscarLugarSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        datos = serializer.validated_data

        try:
            resultados = (
                buscar_lugares_google(
                    consulta=datos[
                        "consulta"
                    ],
                    origen_latitud=datos[
                        "origen_latitud"
                    ],
                    origen_longitud=datos[
                        "origen_longitud"
                    ],
                    radio_metros=datos[
                        "radio_metros"
                    ],
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "consulta": datos[
                    "consulta"
                ],
                "origen": {
                    "latitud": datos[
                        "origen_latitud"
                    ],
                    "longitud": datos[
                        "origen_longitud"
                    ],
                },
                "cantidad": len(
                    resultados
                ),
                "resultados": resultados,
            },
            status=status.HTTP_200_OK,
        )