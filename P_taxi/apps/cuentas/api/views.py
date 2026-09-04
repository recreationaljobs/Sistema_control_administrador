"""Vistas de cuentas móviles."""
from rest_framework import status
from rest_framework.authtoken.models import (
    Token,
)

from rest_framework.permissions import (
    AllowAny,IsAuthenticated,
)
from rest_framework.response import Response

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from App_taxi.api.serializers import (
    UsuarioSerializer,
)
from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
)

from apps.cuentas.models import (
    VinculacionConductor,
)

from .serializers import (
    ActivarConductorSerializer,
    RegistroConductorSerializer,
)

class ActivarConductorThrottle(
    SimpleRateThrottle
):
    scope = "activar_conductor"

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

        token = str(
            request.data.get(
                "token_invitacion",
                "",
            )
        ).strip()[:50]

        ident = (
            f"{identificador}:"
            f"{token or 'sin-token'}"
        )

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class ActivarConductorView(APIView):
    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    throttle_classes = [
        ActivarConductorThrottle,
    ]

    def post(self, request):
        serializer = (
            ActivarConductorSerializer(
                data=request.data,
                context={
                    "request": request,
                },
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        conductor = serializer.save()
        usuario = conductor.usuario

        token, _creado = (
            Token.objects
            .get_or_create(
                user=usuario
            )
        )

        return Response(
            {
                "mensaje": (
                    "La cuenta del conductor "
                    "fue activada correctamente."
                ),
                "token": token.key,
                "rol": (
                    usuario.rol.codigo
                    if usuario.rol
                    else None
                ),
                "usuario": (
                    UsuarioSerializer(
                        usuario
                    ).data
                ),
                "conductor": {
                    "id": conductor.id,
                    "nombre": conductor.nombre,
                    "apellido": conductor.apellido,
                    "telefono": conductor.telefono,
                    "cedula": conductor.cedula,
                    "sucursal": (
                        conductor.sucursal_id
                    ),
                    "sucursal_nombre": (
                        conductor.sucursal.nombre
                        if conductor.sucursal
                        else None
                    ),
                    "activo": conductor.activo,
                },
            },
            status=status.HTTP_200_OK,
        )

class RegistroConductorView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        serializer = RegistroConductorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conductor = serializer.save()
        usuario = conductor.usuario

        token, _ = Token.objects.get_or_create(user=usuario)

        return Response(
            {
                "mensaje": (
                    "Cuenta creada correctamente. "
                    "El conductor está pendiente de aprobación."
                ),
                "token": token.key,
                "usuario": {
                    "id": usuario.id,
                    "username": usuario.username,
                    "nombre": usuario.first_name,
                    "apellido": usuario.last_name,
                    "telefono": usuario.telefono,
                    "rol": usuario.rol.codigo if usuario.rol else None,
                },
                "conductor": {
                    "id": conductor.id,
                    "sucursal_id": conductor.sucursal_id,
                    "vehiculo_id": None,
                    "activo": conductor.activo,
                    "estado_verificacion": conductor.estado_verificacion,
                },
            },
            status=status.HTTP_201_CREATED,
        )

class MiPerfilConductorView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        conductor = (
            Conductor.objects
            .select_related(
                "usuario",
                "usuario__rol",
                "sucursal",
            )
            .filter(
                usuario=request.user
            )
            .first()
        )

        if not conductor:
            return Response(
                {
                    "detail": (
                        "La cuenta no tiene un perfil "
                        "de conductor."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        vinculacion = (
            VinculacionConductor.objects
            .select_related("sucursal")
            .filter(
                conductor=conductor,
                estado="activa",
            )
            .first()
        )

        asignacion = (
            AsignacionVehiculo.objects
            .select_related(
                "vehiculo",
                "vehiculo__estado",
                "vehiculo__tipo_vehiculo",
            )
            .filter(
                conductor=conductor,
                activa=True,
            )
            .first()
        )

        vehiculo = (
            asignacion.vehiculo
            if asignacion
            else None
        )

        conductor_aprobado = (
            conductor.estado_verificacion
            == "aprobado"
            and conductor.activo
        )

        vehiculo_aprobado = (
            vehiculo is not None
            and vehiculo.estado_verificacion
            == "aprobado"
        )

        puede_trabajar = (
            conductor_aprobado
            and vehiculo_aprobado
            and asignacion is not None
        )

        if (
            conductor.estado_verificacion
            == "pendiente"
        ):
            estado_app = "conductor_pendiente"

        elif (
            conductor.estado_verificacion
            == "rechazado"
        ):
            estado_app = "conductor_rechazado"

        elif (
            conductor.estado_verificacion
            == "suspendido"
        ):
            estado_app = "conductor_suspendido"

        elif not vehiculo:
            estado_app = "sin_vehiculo"

        elif (
            vehiculo.estado_verificacion
            == "pendiente"
        ):
            estado_app = "vehiculo_pendiente"

        elif (
            vehiculo.estado_verificacion
            == "rechazado"
        ):
            estado_app = "vehiculo_rechazado"

        elif (
            vehiculo.estado_verificacion
            == "suspendido"
        ):
            estado_app = "vehiculo_suspendido"

        elif puede_trabajar:
            estado_app = "listo_para_trabajar"

        else:
            estado_app = "configuracion_incompleta"

        return Response(
            {
                "usuario": {
                    "id": request.user.id,
                    "username": (
                        request.user.username
                    ),
                    "nombre": (
                        request.user.first_name
                    ),
                    "apellido": (
                        request.user.last_name
                    ),
                    "telefono": (
                        request.user.telefono
                    ),
                    "rol": (
                        request.user.rol.codigo
                        if request.user.rol
                        else None
                    ),
                },
                "conductor": {
                    "id": conductor.id,
                    "nombre": conductor.nombre,
                    "apellido": conductor.apellido,
                    "telefono": conductor.telefono,
                    "cedula": conductor.cedula,
                    "estado_verificacion": (
                        conductor
                        .estado_verificacion
                    ),
                    "activo": conductor.activo,
                },
                "sucursal": (
                    {
                        "id": conductor.sucursal.id,
                        "nombre": (
                            conductor.sucursal.nombre
                        ),
                    }
                    if conductor.sucursal
                    else None
                ),
                "vinculacion": (
                    {
                        "id": vinculacion.id,
                        "tipo": (
                            vinculacion
                            .tipo_vinculacion
                        ),
                        "estado": (
                            vinculacion.estado
                        ),
                        "fecha_inicio": (
                            vinculacion.fecha_inicio
                        ),
                    }
                    if vinculacion
                    else None
                ),
                "vehiculo": (
                    {
                        "id": vehiculo.id,
                        "placa": vehiculo.placa,
                        "marca": vehiculo.marca,
                        "modelo": vehiculo.modelo,
                        "anio": vehiculo.anio,
                        "color": vehiculo.color,
                        "tipo_propiedad": (
                            vehiculo.tipo_propiedad
                        ),
                        "es_propietario": (
                            vehiculo
                            .propietario_conductor_id
                            == conductor.id
                        ),
                        "estado_verificacion": (
                            vehiculo
                            .estado_verificacion
                        ),
                        "estado_operativo": (
                            vehiculo.estado.codigo
                            if vehiculo.estado
                            else None
                        ),
                        "tipo_vehiculo": (
                            {
                                "id": (
                                    vehiculo
                                    .tipo_vehiculo_id
                                ),
                                "codigo": (
                                    vehiculo
                                    .tipo_vehiculo
                                    .codigo
                                ),
                                "nombre": (
                                    vehiculo
                                    .tipo_vehiculo
                                    .nombre
                                ),
                            }
                            if vehiculo.tipo_vehiculo
                            else None
                        ),
                    }
                    if vehiculo
                    else None
                ),
                "puede_trabajar": puede_trabajar,
                "estado_app": estado_app,
            },
            status=status.HTTP_200_OK,
        )