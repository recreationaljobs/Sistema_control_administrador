"""Vistas de pasajeros."""

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import (
    SimpleRateThrottle,
)
from rest_framework.views import APIView

from ..models import Pasajero
from .serializers import (
    PasajeroSerializer,
    RegistroPasajeroSerializer,
)


class RegistroPasajeroThrottle(
    SimpleRateThrottle
):
    scope = "registro_pasajero"

    def get_rate(self):
        return "5/minute"

    def get_cache_key(
        self,
        request,
        view,
    ):
        identificador = self.get_ident(
            request
        )

        return self.cache_format % {
            "scope": self.scope,
            "ident": identificador,
        }


class RegistroPasajeroView(APIView):
    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    throttle_classes = [
        RegistroPasajeroThrottle,
    ]

    def post(self, request):
        serializer = (
            RegistroPasajeroSerializer(
                data=request.data,
                context={
                    "request": request,
                },
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        pasajero = serializer.save()

        pasajero_data = PasajeroSerializer(
            pasajero,
            context={
                "request": request,
            },
        ).data

        return Response(
            {
                "mensaje": (
                    "La cuenta del pasajero "
                    "fue creada correctamente."
                ),
                "pasajero": pasajero_data,
            },
            status=status.HTTP_201_CREATED,
        )


class MiPerfilPasajeroView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get_pasajero(
        self,
        usuario,
    ):
        try:
            return (
                Pasajero.objects
                .select_related("usuario")
                .get(usuario=usuario)
            )
        except Pasajero.DoesNotExist:
            raise NotFound(
                "El usuario autenticado no tiene "
                "un perfil de pasajero."
            )

    def get(self, request):
        pasajero = self.get_pasajero(
            request.user
        )

        serializer = PasajeroSerializer(
            pasajero,
            context={
                "request": request,
            },
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )