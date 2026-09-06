from rest_framework.permissions import AllowAny # type: ignore
from rest_framework.response import Response # pyright: ignore[reportMissingImports]
from rest_framework.views import APIView # type: ignore

from App_taxi.models import ConfiguracionSistema


class EstadoAPIView(APIView):
    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "nombre": "Topo API",
                "version": "v1",
                "estado": "activa",
            }
        )

class VersionAppAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        configuracion = (
            ConfiguracionSistema.objects
            .filter(sucursal__isnull=True)
            .order_by("id")
            .first()
        )

        if configuracion is None:
            return Response(
                {
                    "plataforma": "android",
                    "version_actual": "1.0.0",
                    "build_actual": 1,
                    "build_minimo": 1,
                    "mensaje": (
                        "Hay una nueva versión "
                        "de Zenda disponible."
                    ),
                    "store_url": "",
                }
            )

        return Response(
            {
                "plataforma": "android",
                "version_actual": (
                    configuracion.app_android_version
                ),
                "build_actual": (
                    configuracion.app_android_build
                ),
                "build_minimo": (
                    configuracion.app_android_build_minimo
                ),
                "mensaje": (
                    configuracion.app_actualizacion_mensaje
                ),
                "store_url": (
                    configuracion.app_play_store_url
                ),
            }
        )