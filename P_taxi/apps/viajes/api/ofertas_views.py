"""Vistas de ofertas de viajes."""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import status
from rest_framework.exceptions import (
    NotFound,
    ValidationError,
    PermissionDenied,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from App_taxi.models import Conductor
from apps.pasajeros.models import Pasajero
from apps.viajes.models import (
    OfertaViaje,
    Viaje,
)
from apps.viajes.ofertas_services import (
    aceptar_contraoferta,
    actualizar_ofertas_vencidas,
    crear_contraoferta,
    rechazar_contraoferta,
    cancelar_contraoferta_conductor,
)

from .ofertas_serializers import (
    CrearOfertaViajeSerializer,
    OfertaViajeSerializer,
)
from .serializers import ViajeSerializer


def obtener_pasajero(usuario):
    pasajero = (
        Pasajero.objects
        .filter(usuario=usuario)
        .first()
    )

    if not pasajero:
        raise ValidationError(
            "La cuenta autenticada no tiene "
            "perfil de pasajero."
        )

    return pasajero


class CrearContraofertaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        entrada = CrearOfertaViajeSerializer(
            data=request.data
        )

        entrada.is_valid(
            raise_exception=True
        )

        conductor = (
            Conductor.objects
            .filter(usuario=request.user)
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta autenticada no tiene "
                "perfil de conductor."
            )

        try:
            oferta = crear_contraoferta(
                viaje_id=viaje_id,
                conductor=conductor,
                monto_propuesto=(
                    entrada.validated_data[
                        "monto_propuesto"
                    ]
                ),
                mensaje=(
                    entrada.validated_data.get(
                        "mensaje",
                        "",
                    )
                ),
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "La contraoferta fue enviada "
                    "al pasajero."
                ),
                "oferta": (
                    OfertaViajeSerializer(
                        oferta
                    ).data
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ListarContraofertasView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        viaje_id,
    ):
        pasajero = obtener_pasajero(
            request.user
        )

        try:
            viaje = Viaje.objects.get(
                pk=viaje_id,
                pasajero=pasajero,
            )
        except Viaje.DoesNotExist:
            raise NotFound(
                "El viaje solicitado no existe."
            )

        actualizar_ofertas_vencidas(
            viaje=viaje
        )

        ofertas = (
            OfertaViaje.objects
            .select_related(
                "conductor",
            )
            .filter(viaje=viaje)
            .order_by(
                "-fecha_creacion"
            )
        )

        return Response(
            {
                "viaje_id": viaje.id,
                "tarifa_estimada": (
                    viaje.tarifa_estimada
                ),
                "ofertas": (
                    OfertaViajeSerializer(
                        ofertas,
                        many=True,
                    ).data
                ),
            }
        )


class AceptarContraofertaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        oferta_id,
    ):
        pasajero = obtener_pasajero(
            request.user
        )

        try:
            oferta, viaje = (
                aceptar_contraoferta(
                    oferta_id=oferta_id,
                    pasajero=pasajero,
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
                    "La contraoferta fue aceptada "
                    "correctamente."
                ),
                "oferta": (
                    OfertaViajeSerializer(
                        oferta
                    ).data
                ),
                "viaje": ViajeSerializer(
                    viaje
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class RechazarContraofertaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        oferta_id,
    ):
        pasajero = obtener_pasajero(
            request.user
        )

        try:
            oferta = rechazar_contraoferta(
                oferta_id=oferta_id,
                pasajero=pasajero,
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "La contraoferta fue rechazada."
                ),
                "oferta": (
                    OfertaViajeSerializer(
                        oferta
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )

class EstadoContraofertaView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        oferta_id,
    ):
        try:
            oferta = (
                OfertaViaje.objects
                .select_related(
                    "viaje",
                    "viaje__pasajero",
                    "conductor",
                )
                .get(pk=oferta_id)
            )
        except OfertaViaje.DoesNotExist:
            raise NotFound(
                "La contraoferta no existe."
            )

        actualizar_ofertas_vencidas(
            viaje=oferta.viaje
        )

        oferta.refresh_from_db()

        es_conductor = (
            oferta.conductor.usuario_id
            == request.user.id
        )

        es_pasajero = (
            oferta.viaje.pasajero.usuario_id
            == request.user.id
        )

        if not (
            es_conductor
            or es_pasajero
        ):
            raise PermissionDenied(
                "No tienes permiso para consultar "
                "esta contraoferta."
            )

        return Response(
            {
                "oferta": (
                    OfertaViajeSerializer(
                        oferta
                    ).data
                ),
                "viaje_estado": (
                    oferta.viaje.estado
                ),
                "tarifa_acordada": (
                    oferta.viaje
                    .tarifa_acordada
                ),
            },
            status=status.HTTP_200_OK,
        )

class CancelarContraofertaConductorView(
    APIView
):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        oferta_id,
    ):
        conductor = (
            Conductor.objects
            .filter(usuario=request.user)
            .first()
        )

        if not conductor:
            raise ValidationError(
                "La cuenta autenticada no tiene "
                "perfil de conductor."
            )

        try:
            oferta = (
                cancelar_contraoferta_conductor(
                    oferta_id=oferta_id,
                    conductor=conductor,
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        return Response(
            {
                "mensaje": (
                    "La contraoferta fue retirada."
                ),
                "oferta": (
                    OfertaViajeSerializer(
                        oferta
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )