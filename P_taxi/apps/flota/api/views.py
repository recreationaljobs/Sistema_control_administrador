"""Vistas de flota."""

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from App_taxi.api.permissions import EsAdminSucursalOSuperAdmin

from ..models import TipoVehiculo
from .serializers import (
    RegistroVehiculoPropioSerializer,
    TipoVehiculoSerializer,
)


class TipoVehiculoViewSet(viewsets.ModelViewSet):
    serializer_class = TipoVehiculoSerializer
    queryset = TipoVehiculo.objects.all()
    filterset_fields = [
        "activo",
        "requiere_casco",
        "permite_equipaje",
    ]
    search_fields = [
        "nombre",
        "codigo",
    ]
    ordering_fields = [
        "orden",
        "nombre",
        "capacidad_pasajeros",
    ]
    ordering = [
        "orden",
        "nombre",
    ]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            return [EsAdminSucursalOSuperAdmin()]

        return [IsAuthenticated()]


class RegistroVehiculoPropioThrottle(SimpleRateThrottle):
    scope = "registro_vehiculo_propio"

    def get_rate(self):
        return "5/hour"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.pk),
        }


class RegistrarVehiculoPropioView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RegistroVehiculoPropioThrottle]

    def post(self, request):
        serializer = RegistroVehiculoPropioSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        vehiculo = serializer.save()
        conductor = vehiculo.propietario_conductor

        return Response(
            {
                "mensaje": (
                    "El vehículo fue registrado correctamente. "
                    "Se activará con la aprobación del conductor."
                ),
                "vehiculo": {
                    "id": vehiculo.id,
                    "numero": vehiculo.numero,
                    "placa": vehiculo.placa,
                    "marca": vehiculo.marca,
                    "modelo": vehiculo.modelo,
                    "anio": vehiculo.anio,
                    "color": vehiculo.color,
                    "tipo_vehiculo": {
                        "id": vehiculo.tipo_vehiculo_id,
                        "codigo": vehiculo.tipo_vehiculo.codigo,
                        "nombre": vehiculo.tipo_vehiculo.nombre,
                    },
                    "tipo_propiedad": vehiculo.tipo_propiedad,
                    "estado_verificacion": (
                        vehiculo.estado_verificacion
                    ),
                    "sucursal_id": vehiculo.sucursal_id,
                    "propietario_conductor_id": conductor.id,
                },
            },
            status=status.HTTP_201_CREATED,
        )
