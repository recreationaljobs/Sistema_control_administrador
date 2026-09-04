"""Vistas de pagos de viajes."""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import status
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.viajes.models import PagoViaje
from apps.viajes.pagos_services import (
    confirmar_pago_efectivo,
)

from .pagos_serializers import (
    PagoViajeSerializer,
)


class ConsultarPagoViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        viaje_id,
    ):
        try:
            pago = (
                PagoViaje.objects
                .select_related(
                    "viaje",
                    "viaje__pasajero",
                    "viaje__conductor",
                )
                .get(viaje_id=viaje_id)
            )
        except PagoViaje.DoesNotExist:
            raise NotFound(
                "El viaje no tiene un pago."
            )

        viaje = pago.viaje
        usuario_id = request.user.id

        es_pasajero = (
            viaje.pasajero.usuario_id
            == usuario_id
        )

        es_conductor = (
            viaje.conductor
            and viaje.conductor.usuario_id
            == usuario_id
        )

        if not (
            es_pasajero
            or es_conductor
        ):
            raise PermissionDenied(
                "No tienes permiso para consultar "
                "este pago."
            )

        return Response(
            PagoViajeSerializer(pago).data,
            status=status.HTTP_200_OK,
        )


class ConfirmarPagoEfectivoView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        try:
            pago, actualizado = (
                confirmar_pago_efectivo(
                    viaje_id=viaje_id,
                    usuario=request.user,
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "Pago en efectivo confirmado."
                    if actualizado
                    else (
                        "El pago ya estaba "
                        "confirmado."
                    )
                ),
                "actualizado": actualizado,
                "pago": (
                    PagoViajeSerializer(
                        pago
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )

class ConfiguracionPagosView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        tarjeta_habilitada = getattr(
            settings,
            "PAGOS_TARJETA_HABILITADOS",
            False,
        )

        return Response(
            {
                "moneda": "NIO",
                "metodos": [
                    {
                        "codigo": "efectivo",
                        "nombre": "Efectivo",
                        "habilitado": True,
                    },
                    {
                        "codigo": "tarjeta",
                        "nombre": "Tarjeta",
                        "habilitado": (
                            tarjeta_habilitada
                        ),
                    },
                ],
            },
            status=status.HTTP_200_OK,
        )