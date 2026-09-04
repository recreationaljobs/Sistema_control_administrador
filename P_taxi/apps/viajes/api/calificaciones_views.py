"""Vistas de calificaciones."""

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

from apps.viajes.calificaciones_services import (
    calificar_viaje,
)
from django.db.models import (
    Avg,
    Count,
)

from apps.viajes.models import (
    CalificacionViaje,
)

from .calificaciones_serializers import (
    CalificacionViajeSerializer,
    CrearCalificacionSerializer,
)


class CalificarViajeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(
        self,
        request,
        viaje_id,
    ):
        entrada = CrearCalificacionSerializer(
            data=request.data
        )

        entrada.is_valid(
            raise_exception=True
        )

        try:
            calificacion = calificar_viaje(
                viaje_id=viaje_id,
                usuario=request.user,
                puntuacion=(
                    entrada.validated_data[
                        "puntuacion"
                    ]
                ),
                comentario=(
                    entrada.validated_data.get(
                        "comentario",
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
                    "La calificación fue registrada "
                    "correctamente."
                ),
                "calificacion": (
                    CalificacionViajeSerializer(
                        calificacion
                    ).data
                ),
            },
            status=status.HTTP_201_CREATED,
        )

class MiResumenCalificacionesView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        calificaciones = (
            CalificacionViaje.objects
            .filter(
                usuario_evaluado=request.user
            )
        )

        resumen = calificaciones.aggregate(
            promedio=Avg("puntuacion"),
            total=Count("id"),
        )

        promedio = resumen["promedio"]

        distribucion_consulta = (
            calificaciones
            .values("puntuacion")
            .annotate(cantidad=Count("id"))
            .order_by("puntuacion")
        )

        distribucion = {
            "1": 0,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 0,
        }

        for elemento in distribucion_consulta:
            distribucion[
                str(elemento["puntuacion"])
            ] = elemento["cantidad"]

        ultimas_calificaciones = (
            calificaciones
            .exclude(comentario="")
            .order_by("-fecha_registro")[:10]
        )

        return Response(
            {
                "promedio": (
                    round(float(promedio), 2)
                    if promedio is not None
                    else 0
                ),
                "total_calificaciones": (
                    resumen["total"]
                ),
                "distribucion": distribucion,
                "ultimas_calificaciones": (
                    CalificacionViajeSerializer(
                        ultimas_calificaciones,
                        many=True,
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )