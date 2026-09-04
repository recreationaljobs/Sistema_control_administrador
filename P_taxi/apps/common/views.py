from rest_framework.permissions import ( # type: ignore
    AllowAny,
)
from rest_framework.response import Response
from rest_framework.views import APIView


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