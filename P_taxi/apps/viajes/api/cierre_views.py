"""Vistas para gestionar el cierre de un viaje."""

from rest_framework.exceptions import (
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
    CalificacionViaje,
    PagoViaje,
    Viaje,
)

from .pagos_serializers import (
    PagoViajeSerializer,
)
from .serializers import ViajeSerializer


class CierrePendienteViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        usuario = request.user

        rol_codigo = (
            usuario.rol.codigo
            if usuario.rol
            else ""
        )

        queryset = (
            Viaje.objects
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "conductor",
                "conductor__usuario",
                "vehiculo",
                "tipo_vehiculo",
                "sucursal",
                "pago",
            )
            .prefetch_related(
                "calificaciones",
            )
            .filter(
                estado="completado",
            )
            .order_by(
                "-fecha_finalizacion",
                "-fecha_solicitud",
            )
        )

        if rol_codigo == "pasajero":
            pasajero = (
                Pasajero.objects
                .filter(
                    usuario=usuario,
                )
                .first()
            )

            if not pasajero:
                return self._respuesta_sin_cierre(
                    tipo_cuenta="pasajero",
                )

            viaje = (
                queryset
                .filter(
                    pasajero=pasajero,
                )
                .first()
            )

            tipo_calificacion = (
                CalificacionViaje
                .PASAJERO_A_CONDUCTOR
            )

            tipo_cuenta = "pasajero"

        elif rol_codigo == "taxista":
            conductor = (
                Conductor.objects
                .filter(
                    usuario=usuario,
                )
                .first()
            )

            if not conductor:
                return self._respuesta_sin_cierre(
                    tipo_cuenta="taxista",
                )

            viaje = (
                queryset
                .filter(
                    conductor=conductor,
                )
                .first()
            )

            tipo_calificacion = (
                CalificacionViaje
                .CONDUCTOR_A_PASAJERO
            )

            tipo_cuenta = "taxista"

        else:
            raise PermissionDenied(
                "Esta cuenta no puede consultar "
                "el cierre de viajes."
            )

        if not viaje:
            return self._respuesta_sin_cierre(
                tipo_cuenta=tipo_cuenta,
            )

        pago = getattr(
            viaje,
            "pago",
            None,
        )

        ya_califico = (
            viaje.calificaciones
            .filter(
                tipo=tipo_calificacion,
            )
            .exists()
        )

        pago_pendiente = (
            pago is not None
            and pago.estado
            == PagoViaje.ESTADO_PENDIENTE
        )

        puede_confirmar_pago = (
            tipo_cuenta == "taxista"
            and pago is not None
            and pago.metodo
            == PagoViaje.METODO_EFECTIVO
            and pago_pendiente
        )

        cierre_pendiente = (
            not ya_califico
            or pago_pendiente
        )

        if not cierre_pendiente:
            return self._respuesta_sin_cierre(
                tipo_cuenta=tipo_cuenta,
            )

        return Response(
            {
                "tipo_cuenta": tipo_cuenta,
                "tiene_cierre_pendiente": True,
                "ya_califico": ya_califico,
                "pago_pendiente": pago_pendiente,
                "puede_confirmar_pago": (
                    puede_confirmar_pago
                ),
                "viaje": ViajeSerializer(
                    viaje,
                    context={
                        "request": request,
                    },
                ).data,
                "pago": (
                    PagoViajeSerializer(
                        pago
                    ).data
                    if pago is not None
                    else None
                ),
            }
        )

    def _respuesta_sin_cierre(
        self,
        *,
        tipo_cuenta,
    ):
        return Response(
            {
                "tipo_cuenta": tipo_cuenta,
                "tiene_cierre_pendiente": False,
                "ya_califico": False,
                "pago_pendiente": False,
                "puede_confirmar_pago": False,
                "viaje": None,
                "pago": None,
            }
        )