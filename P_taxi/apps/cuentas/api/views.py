"""Vistas de cuentas móviles."""
from rest_framework import status # type: ignore
from rest_framework.authtoken.models import ( # type: ignore
    Token,
)
from rest_framework.parsers import ( # type: ignore
    FormParser,
    MultiPartParser,
)

from rest_framework.permissions import ( # type: ignore
    AllowAny,IsAuthenticated,
)
from rest_framework.response import Response # type: ignore

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle # type: ignore
from rest_framework.views import APIView # type: ignore
from django.core.exceptions import ValidationError as DjangoValidationError # type: ignore
from django.db import transaction # type: ignore

from rest_framework.exceptions import ValidationError # pyright: ignore[reportMissingImports]
from App_taxi.verification_services import (
    aprobar_conductor_completo,
)

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
    FotoPerfilSerializer,
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
        serializer = RegistroConductorSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            with transaction.atomic():
                # 1. Crear usuario, conductor y vehículo.
                conductor = serializer.save()

                # 2. Aprobar inmediatamente todo el registro.
                conductor, vehiculo, asignacion = (
                    aprobar_conductor_completo(
                        conductor.id
                    )
                )

                usuario = conductor.usuario

                # 3. Crear token.
                token, _ = Token.objects.get_or_create(
                    user=usuario
                )

        except DjangoValidationError as error:
            raise ValidationError(
                {
                    "detail": (
                        error.messages[0]
                        if error.messages
                        else str(error)
                    )
                }
            )

        return Response(
            {
                "mensaje": (
                    "Cuenta creada correctamente. "
                    "El conductor y su vehículo "
                    "han sido aprobados y ya pueden trabajar."
                ),
                "token": token.key,

                "usuario": {
                    "id": usuario.id,
                    "username": usuario.username,
                    "nombre": usuario.first_name,
                    "apellido": usuario.last_name,
                    "telefono": usuario.telefono,
                    "rol": (
                        usuario.rol.codigo
                        if usuario.rol
                        else None
                    ),
                },

                "conductor": {
                    "id": conductor.id,
                    "sucursal_id": conductor.sucursal_id,
                    "activo": conductor.activo,
                    "estado_verificacion": (
                        conductor.estado_verificacion
                    ),
                },

                "vehiculo": {
                    "id": vehiculo.id,
                    "tipo_vehiculo_id": (
                        vehiculo.tipo_vehiculo_id
                    ),
                    "numero": vehiculo.numero,
                    "placa": vehiculo.placa,
                    "marca": vehiculo.marca,
                    "modelo": vehiculo.modelo,
                    "anio": vehiculo.anio,
                    "color": vehiculo.color,
                    "estado_verificacion": (
                        vehiculo.estado_verificacion
                    ),
                    "estado": (
                        vehiculo.estado.codigo
                        if vehiculo.estado
                        else None
                    ),
                },

                "asignacion": {
                    "id": asignacion.id,
                    "activa": asignacion.activa,
                    "vehiculo_id": (
                        asignacion.vehiculo_id
                    ),
                    "conductor_id": (
                        asignacion.conductor_id
                    ),
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
                    "foto_perfil_url": (
                        request.build_absolute_uri(
                            request.user.foto_perfil.url
                        )
                        if request.user.foto_perfil
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

class FotoPerfilView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def get(self, request):
        usuario = request.user

        foto_url = None

        if (
            hasattr(usuario, "foto_perfil")
            and usuario.foto_perfil
        ):
            foto_url = request.build_absolute_uri(
                usuario.foto_perfil.url
            )

        return Response(
        {
            "usuario_id": usuario.id,
            "nombre": usuario.first_name,
            "apellido": usuario.last_name,
            "telefono": usuario.telefono,
            "email": usuario.email,
            "rol": (
                usuario.rol.codigo
                if usuario.rol
                else None
            ),
            "foto_perfil_url": foto_url,
        },
        status=status.HTTP_200_OK,
    )

    def patch(self, request):
        serializer = FotoPerfilSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        usuario = request.user
        nueva_foto = serializer.validated_data[
            "foto"
        ]

        # Elimina físicamente la foto anterior.
        if (
            hasattr(usuario, "foto_perfil")
            and usuario.foto_perfil
        ):
            usuario.foto_perfil.delete(
                save=False
            )

        usuario.foto_perfil = nueva_foto
        usuario.save(
            update_fields=[
                "foto_perfil",
            ]
        )

        foto_url = request.build_absolute_uri(
            usuario.foto_perfil.url
        )

        return Response(
            {
                "mensaje": (
                    "Foto de perfil actualizada "
                    "correctamente."
                ),
                "foto_perfil_url": foto_url,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        usuario = request.user

        if (
            not hasattr(usuario, "foto_perfil")
            or not usuario.foto_perfil
        ):
            return Response(
                {
                    "detail": (
                        "El usuario no tiene una "
                        "foto de perfil."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.foto_perfil.delete(
            save=False
        )

        usuario.foto_perfil = None

        usuario.save(
            update_fields=[
                "foto_perfil",
            ]
        )

        return Response(
            {
                "mensaje": (
                    "Foto de perfil eliminada "
                    "correctamente."
                )
            },
            status=status.HTTP_200_OK,
        )
