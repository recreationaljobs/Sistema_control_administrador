from decimal import Decimal, InvalidOperation
import logging
from django.contrib.auth import authenticate  # type: ignore[reportMissingModuleSource]
from django.core.exceptions import ValidationError as DjangoValidationError  # type: ignore[reportMissingModuleSource]
from django.db import transaction   # type: ignore[reportMissingModuleSource]
from django.db.models import Prefetch, Q, Sum, DecimalField ,Count,Max # type: ignore[reportMissingModuleSource]
from django.db.models.functions import Coalesce # type: ignore[reportMissingModuleSource]
from django.db.models import Value # type: ignore[reportMissingModuleSource]
from django.utils import timezone # type: ignore[reportMissingModuleSource]
from django.utils.dateparse import parse_date # type: ignore[reportMissingModuleSource]
from django.http import HttpResponse # type: ignore[reportMissingModuleSource]
from rest_framework.pagination import PageNumberPagination # type: ignore[reportMissingModuleSource]
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from apps.cuentas.services import (
    desvincular_conductor_de_sucursal,
    vincular_conductor_a_sucursal,
)

from openpyxl import Workbook # type: ignore[reportMissingModuleSource]
from openpyxl.styles import ( # type: ignore[reportMissingModuleSource]
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter # type: ignore[reportMissingModuleSource]


from rest_framework import status, viewsets # type: ignore[reportMissingModuleSource]
from django.db.models.functions import TruncMonth   # type: ignore[reportMissingModuleSource]
from rest_framework.authtoken.models import Token   # type: ignore[reportMissingModuleSource]
from rest_framework.decorators import action    # type: ignore[reportMissingModuleSource]
from rest_framework.exceptions import PermissionDenied, ValidationError # type: ignore[reportMissingModuleSource]
from rest_framework.permissions import AllowAny, IsAuthenticated    # type: ignore[reportMissingModuleSource]
from rest_framework.response import Response    # type: ignore[reportMissingModuleSource]
from rest_framework.views import APIView    # type: ignore[reportMissingModuleSource]
from App_taxi.models import (
    DispositivoNotificacion,
)

from App_taxi.email_services import (
    enviar_correo_usuario_creado,
)

from ..models import (
    Sucursal,
    Rol,
    Usuario,
    EstadoVehiculo,
    EstadoJornada,
    TipoGasto,
    EstadoGasto,
    EstadoAdelanto,
    TipoMantenimiento,
    EstadoMantenimiento,
    Conductor,
    Vehiculo,
    DocumentoVehiculo,
    AsignacionVehiculo,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Mantenimiento,
    ConfiguracionSistema,
    Liquidacion,
    DetalleLiquidacion,
    MovimientoAuditoria,
)

from .serializers import (
    SucursalSerializer,
    RolSerializer,
    UsuarioSerializer,
    EstadoVehiculoSerializer,
    EstadoJornadaSerializer,
    TipoGastoSerializer,
    EstadoGastoSerializer,
    EstadoAdelantoSerializer,
    TipoMantenimientoSerializer,
    EstadoMantenimientoSerializer,
    ConductorSerializer,
    VehiculoSerializer,
    DocumentoVehiculoSerializer,
    AsignacionVehiculoSerializer,
    JornadaDiariaSerializer,
    GastoSerializer,
    AdelantoSerializer,
    MantenimientoSerializer,
    ConfiguracionSistemaSerializer,
    MovimientoAuditoriaSerializer,
    
)

from rest_framework.throttling import SimpleRateThrottle    # type: ignore[reportMissingModuleSource]

from .permissions import (
    EsSuperAdmin,
    EsAdminSucursalOSuperAdmin,
    es_superadmin,
    es_admin_sucursal,
    es_taxista,
    rol_codigo,
)

from .services import (
    obtener_configuracion_sucursal,
    obtener_rango_periodo,
    calcular_campos_jornada,
    recalcular_totales_jornada,
    actualizar_kilometraje_vehiculo,
    aplicar_mantenimiento_en_vehiculo,
    obtener_alertas_vehiculo,
    construir_alerta_km_aceite,
    construir_alerta_licencia,
    sumar_decimal,
    sumar_entero,
)

logger = logging.getLogger(__name__)
class RegistrarDispositivoNotificacionView(APIView):
    permission_classes = [IsAuthenticated]
    ROLES_PERMITIDOS = {
    "pasajero",
    "taxista",
    "admin_sucursal",
    "superadmin",
    "super_admin",
}

    def post(self, request):
        usuario = request.user

        codigo_rol = str(
            getattr(
                getattr(
                    usuario,
                    "rol",
                    None,
                ),
                "codigo",
                "",
            )
            or ""
        ).strip().lower()

        if codigo_rol not in self.ROLES_PERMITIDOS:
            return Response(
                {
                    "detail": (
                        "Tu usuario no tiene permiso para "
                        "activar notificaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            codigo_rol == "admin_sucursal"
            and not usuario.sucursal_id
        ):
            return Response(
                {
                    "detail": (
                        "Tu usuario administrador no tiene "
                        "una sucursal asignada."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = str(
            request.data.get("token") or ""
        ).strip()

        if not token:
            return Response(
                {
                    "token": (
                        "Debes enviar el token "
                        "del dispositivo."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispositivo, creado = (
            DispositivoNotificacion.objects
            .update_or_create(
                token=token,
                defaults={
                    "usuario": usuario,
                    "activo": True,
                },
            )
        )

        if codigo_rol == "pasajero":
            tipo_notificaciones = (
                "Recibirás actualizaciones de tus "
                "viajes y nuevas contraofertas."
            )
        elif codigo_rol == "taxista":
            tipo_notificaciones = (
                "Recibirás recordatorios para abrir y cerrar "
                "tu jornada, además de alertas del próximo "
                "cambio de aceite del vehículo asignado."
            )

        elif codigo_rol == "admin_sucursal":
            tipo_notificaciones = (
                "Recibirás alertas de mantenimiento "
                "y cambio de aceite únicamente de los "
                "vehículos registrados en tu sucursal."
            )

        else:
            tipo_notificaciones = (
                "Recibirás alertas de mantenimiento "
                "y cambio de aceite únicamente de los "
                "vehículos sin sucursal que pertenecen "
                "al panel del superadministrador."
            )

        return Response(
            {
                "detail": (
                    "Notificaciones activadas "
                    "correctamente."
                ),
                "tipo_notificaciones": (
                    tipo_notificaciones
                ),
                "dispositivo_id": dispositivo.id,
                "creado": creado,
                "rol": codigo_rol,
                "sucursal": (
                    usuario.sucursal_id
                    if usuario.sucursal_id
                    else None
                ),
            },
            status=(
                status.HTTP_201_CREATED
                if creado
                else status.HTTP_200_OK
            ),
        )

class DesactivarDispositivoNotificacionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = str(
            request.data.get("token") or ""
        ).strip()

        if not token:
            return Response(
                {
                    "token": (
                        "Debes enviar el token "
                        "del dispositivo."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        actualizados = (
            DispositivoNotificacion.objects
            .filter(
                usuario=request.user,
                token=token,
            )
            .update(
                activo=False
            )
        )

        return Response(
            {
                "detail": (
                    "Notificaciones desactivadas."
                ),
                "actualizados": actualizados,
            },
            status=status.HTTP_200_OK,
        )

class LoginRateThrottle(SimpleRateThrottle):
    """Limita los intentos de inicio de sesión por IP y usuario."""

    scope = "login"
    rate = "5/min"

    def get_cache_key(self, request, view):
        ip = self.get_ident(request)
        username = str(
            request.data.get("username", "")
        ).strip().lower()[:150]

        ident = f"{ip}:{username or 'sin-usuario'}"

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        identificador = str(
            request.data.get("username", "")
        ).strip()

        password = str(
            request.data.get("password", "")
        )

        if not identificador or not password:
            return Response(
                {
                    "detail": (
                        "Debes ingresar usuario, correo "
                        "o teléfono y contraseña."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidatos = Usuario.objects.none()

        # Buscar por username
        candidatos = candidatos | Usuario.objects.filter(
            username__iexact=identificador
        )

        # Buscar por correo
        candidatos = candidatos | Usuario.objects.filter(
            email__iexact=identificador
        ).exclude(
            email=""
        )

        # Buscar por teléfono
        digitos = "".join(
            c for c in identificador
            if c.isdigit()
        )

        variantes_telefono = {
            identificador,
        }

        if digitos:
            variantes_telefono.add(digitos)
            variantes_telefono.add(f"+{digitos}")

            if len(digitos) == 8:
                variantes_telefono.add(
                    f"505{digitos}"
                )

                variantes_telefono.add(
                    f"+505{digitos}"
                )

            if (
                len(digitos) == 11
                and digitos.startswith("505")
            ):
                variantes_telefono.add(
                    digitos[-8:]
                )

                variantes_telefono.add(
                    f"+{digitos}"
                )

        consulta_telefono = Q()

        for telefono in variantes_telefono:
            consulta_telefono |= Q(
                telefono__iexact=telefono
            )

        candidatos = (
            candidatos
            | Usuario.objects.filter(
                consulta_telefono
            )
        )

        candidatos = (
            candidatos
            .select_related(
                "rol",
                "sucursal",
            )
            .distinct()
            .order_by("id")
        )

        user = None

        for candidato in candidatos:
            if candidato.check_password(password):
                user = candidato
                break

        if user is None:
            return Response(
                {
                    "detail": (
                        "Usuario, correo o teléfono "
                        "o contraseña incorrectos."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {
                    "detail": (
                        "Este usuario está inactivo. "
                        "Contacta al administrador."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.rol:
            return Response(
                {
                    "detail": (
                        "Este usuario no tiene "
                        "un rol asignado."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            user.rol.codigo == "admin_sucursal"
            and not user.sucursal
        ):
            return Response(
                {
                    "detail": (
                        "Este usuario no tiene "
                        "una sucursal asignada."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        token, _ = Token.objects.get_or_create(
            user=user
        )

        return Response(
            {
                "token": token.key,
                "user": UsuarioSerializer(user).data,
                "rol": user.rol.codigo,
                "sucursal": (
                    user.sucursal.id
                    if user.sucursal
                    else None
                ),
                "sucursal_nombre": (
                    user.sucursal.nombre
                    if user.sucursal
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(
            {"detail": "Sesión cerrada correctamente."},
            status=status.HTTP_200_OK
        )


class MiPerfilView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(
            UsuarioSerializer(request.user).data,
            status=status.HTTP_200_OK
        )
    

class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.all().order_by("nombre")
    serializer_class = SucursalSerializer
    permission_classes = [EsSuperAdmin]


class RolViewSet(viewsets.ModelViewSet):
    serializer_class = RolSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [EsAdminSucursalOSuperAdmin()]

        return [EsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user

        queryset = Rol.objects.all().order_by("nombre")

        if es_superadmin(user):
            return queryset

        if es_admin_sucursal(user):
            return queryset.filter(codigo="taxista")

        return Rol.objects.none()


class EstadoVehiculoViewSet(viewsets.ModelViewSet):
    queryset = EstadoVehiculo.objects.all().order_by("nombre")
    serializer_class = EstadoVehiculoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [EsSuperAdmin()]


class EstadoJornadaViewSet(viewsets.ModelViewSet):
    queryset = EstadoJornada.objects.all().order_by("nombre")
    serializer_class = EstadoJornadaSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [EsSuperAdmin()]


class TipoGastoViewSet(viewsets.ModelViewSet):
    queryset = TipoGasto.objects.all().order_by("nombre")
    serializer_class = TipoGastoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsSuperAdmin()]

class EstadoGastoViewSet(viewsets.ModelViewSet):
    queryset = EstadoGasto.objects.all().order_by("nombre")
    serializer_class = EstadoGastoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsSuperAdmin()]


class EstadoAdelantoViewSet(viewsets.ModelViewSet):
    queryset = EstadoAdelanto.objects.all().order_by("nombre")
    serializer_class = EstadoAdelantoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [EsSuperAdmin()]


class TipoMantenimientoViewSet(viewsets.ModelViewSet):
    queryset = TipoMantenimiento.objects.all().order_by("nombre")
    serializer_class = TipoMantenimientoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [EsSuperAdmin()]


class EstadoMantenimientoViewSet(viewsets.ModelViewSet):
    queryset = EstadoMantenimiento.objects.all().order_by("nombre")
    serializer_class = EstadoMantenimientoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        return [EsSuperAdmin()]


class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action in ["me"]:
            return [IsAuthenticated()]

        if self.action in ["dar_baja", "reactivar"]:
            return [EsSuperAdmin()]

        return [EsAdminSucursalOSuperAdmin()]

    def get_queryset(self):
        user = self.request.user

        queryset = Usuario.objects.select_related(
            "rol",
            "sucursal"
        ).all().order_by("-id")

        if es_superadmin(user):
            # El superadministrador no verá taxistas que
            # pertenezcan a una sucursal.
            #
            # Sí seguirá viendo:
            # - superadmin
            # - usuario_sistema
            # - admin_sucursal
            # - taxistas sin sucursal
            return queryset.exclude(
                rol__codigo="taxista",
                sucursal__isnull=False
            )

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                return queryset.none()

            # El administrador de sucursal solamente puede
            # ver los taxistas de su propia sucursal.
            return queryset.filter(
                sucursal_id=user.sucursal_id,
                rol__codigo="taxista"
            )

        # Cualquier otro usuario solo puede consultar
        # su propia cuenta.
        return queryset.filter(id=user.id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(self.get_serializer(request.user).data)

    @action(detail=True, methods=["post"], url_path="dar-baja")
    def dar_baja(self, request, pk=None):
        usuario = self.get_object()

        # Proteccion: no se puede dar de baja a un superadmin.
        if es_superadmin(usuario):
            raise PermissionDenied("No puedes dar de baja a un superadmin.")

        usuario.is_active = False
        usuario.save(update_fields=["is_active"])

        # Revoca los tokens activos para forzar el cierre de sesion.
        Token.objects.filter(user=usuario).delete()

        return Response(
            self.get_serializer(usuario).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="reactivar")
    def reactivar(self, request, pk=None):
        usuario = self.get_object()

        usuario.is_active = True
        usuario.save(update_fields=["is_active"])

        return Response(
            self.get_serializer(usuario).data,
            status=status.HTTP_200_OK
        )
    

    def create(
        self,
        request,
        *args,
        **kwargs
    ):
        password_plano = str(
            request.data.get(
                "password",
                ""
            )
        ).strip()

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        # /*
        # * No se reemplaza perform_create.
        # * Se sigue llamando para conservar
        # * las reglas de permisos y sucursal.
        # */
        self.perform_create(serializer)

        usuario = serializer.instance

        correo_enviado = False
        error_correo = None

        correo_usuario = (
            usuario.email or ""
        ).strip()

        if correo_usuario and password_plano:
            try:
                correo_enviado = (
                    enviar_correo_usuario_creado(
                        usuario=usuario,
                        password_plano=password_plano,
                    )
                )
            except Exception as error:
                error_correo = str(error)

                logger.exception(
                    "No se pudo enviar el correo "
                    "de registro al usuario %s.",
                    usuario.id,
                )

        headers = self.get_success_headers(
            serializer.data
        )

        respuesta = dict(
            serializer.data
        )

        respuesta["correo_enviado"] = (
            correo_enviado
        )

        respuesta["correo_destino"] = (
            correo_usuario
            if correo_usuario
            else None
        )

        if error_correo:
            respuesta["correo_error"] = (
                "El usuario fue creado, "
                "pero no se pudo enviar el correo."
            )

        return Response(
            respuesta,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )



    def perform_create(self, serializer):
        user = self.request.user
        rol = serializer.validated_data.get("rol")

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                raise ValidationError(
                    "Tu usuario no tiene una sucursal asignada."
                )

            if not rol or rol.codigo != "taxista":
                raise PermissionDenied(
                    "Un administrador de sucursal solo puede crear usuarios taxistas."
                )

            # La sucursal siempre se toma del administrador
            # autenticado, nunca del frontend.
            serializer.save(
                sucursal=user.sucursal
            )
            return


    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        rol = serializer.validated_data.get("rol", instance.rol)

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                raise ValidationError(
                    "Tu usuario no tiene una sucursal asignada."
                )

            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes modificar usuarios de otra sucursal."
                )

            if not rol or rol.codigo != "taxista":
                raise PermissionDenied(
                    "Un administrador de sucursal solo puede modificar usuarios taxistas."
                )

            # Impide que el usuario sea trasladado a otra
            # sucursal enviando otro ID desde el frontend.
            serializer.save(
                sucursal=user.sucursal
            )
            return

    @action(
        detail=False,
        methods=["post"],
        url_path="vincular-sucursal",
        permission_classes=[
            EsAdminSucursalOSuperAdmin
        ],
    )
    def vincular_sucursal(
        self,
        request,
    ):
        usuario = request.user

        conductor_id = request.data.get(
            "conductor_id"
        )

        tipo_vinculacion = str(
            request.data.get(
                "tipo_vinculacion",
                "empleado",
            )
        ).strip()

        if not conductor_id:
            raise ValidationError({
                "conductor_id": (
                    "Debes seleccionar un conductor."
                )
            })

        if tipo_vinculacion not in [
            "empleado",
            "afiliado",
        ]:
            raise ValidationError({
                "tipo_vinculacion": (
                    "El tipo debe ser empleado "
                    "o afiliado."
                )
            })

        try:
            conductor = (
                Conductor.objects
                .select_related(
                    "usuario",
                    "sucursal",
                )
                .get(pk=conductor_id)
            )
        except Conductor.DoesNotExist:
            raise ValidationError({
                "conductor_id": (
                    "El conductor seleccionado "
                    "no existe."
                )
            })

        if conductor.sucursal_id:
            raise ValidationError({
                "conductor_id": (
                    "El conductor ya pertenece "
                    "a una sucursal."
                )
            })

        if es_admin_sucursal(usuario):
            if not usuario.sucursal_id:
                raise PermissionDenied(
                    "Tu cuenta no tiene una "
                    "sucursal asignada."
                )

            sucursal = usuario.sucursal

        elif es_superadmin(usuario):
            sucursal_id = request.data.get(
                "sucursal_id"
            )

            if not sucursal_id:
                raise ValidationError({
                    "sucursal_id": (
                        "Debes seleccionar "
                        "una sucursal."
                    )
                })

            try:
                sucursal = Sucursal.objects.get(
                    pk=sucursal_id
                )
            except Sucursal.DoesNotExist:
                raise ValidationError({
                    "sucursal_id": (
                        "La sucursal seleccionada "
                        "no existe."
                    )
                })

        else:
            raise PermissionDenied(
                "No tienes permiso para "
                "vincular conductores."
            )

        try:
            vinculacion = (
                vincular_conductor_a_sucursal(
                    conductor=conductor,
                    sucursal=sucursal,
                    usuario=usuario,
                    tipo_vinculacion=(
                        tipo_vinculacion
                    ),
                )
            )
        except DjangoValidationError as error:
            raise ValidationError(
                error.messages
            )

        conductor.refresh_from_db()

        return Response(
            {
                "mensaje": (
                    "El conductor fue vinculado "
                    "a la sucursal correctamente."
                ),
                "vinculacion": {
                    "id": vinculacion.id,
                    "estado": vinculacion.estado,
                    "tipo_vinculacion": (
                        vinculacion.tipo_vinculacion
                    ),
                    "sucursal_id": (
                        vinculacion.sucursal_id
                    ),
                    "conductor_id": (
                        vinculacion.conductor_id
                    ),
                },
                "conductor": (
                    self.get_serializer(
                        conductor
                    ).data
                ),
            },
            status=status.HTTP_200_OK,
        )

class ConductorViewSet(viewsets.ModelViewSet):
    serializer_class = ConductorSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]

        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        qs = (
            Conductor.objects
            .select_related(
                "sucursal",
                "usuario",
            )
            .all()
            .order_by("-id")
        )

        if es_superadmin(user):
            return qs.filter(
                sucursal__isnull=True
            )

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                return qs.none()

            return qs.filter(
                sucursal_id=user.sucursal_id
            )

        if es_taxista(user):
            return qs.filter(
                usuario=user
            )

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user

        # Si no se envia porcentaje_pago, se usa el % por defecto de la sucursal.
        porcentaje = serializer.validated_data.get("porcentaje_pago")

        if es_superadmin(user):
            if porcentaje is None:
                porcentaje = obtener_configuracion_sucursal(None).porcentaje_pago_conductor
            serializer.save(sucursal=None, porcentaje_pago=porcentaje)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if porcentaje is None:
                porcentaje = obtener_configuracion_sucursal(user.sucursal).porcentaje_pago_conductor
            serializer.save(sucursal=user.sucursal, porcentaje_pago=porcentaje)
            return

        raise PermissionDenied("No tienes permiso para crear conductores.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        # El % solo se toca si llega en el request. Si llega null/vacio -> default
        # de la sucursal; si llega con valor (incluido 0 explicito) se respeta;
        # si no llega, se conserva el valor actual del conductor.
        actualizar_porcentaje = "porcentaje_pago" in serializer.validated_data
        porcentaje = serializer.validated_data.get("porcentaje_pago")

        if es_superadmin(user):
            sucursal = serializer.validated_data.get("sucursal", instance.sucursal)

            if actualizar_porcentaje and porcentaje is None:
                porcentaje = obtener_configuracion_sucursal(sucursal).porcentaje_pago_conductor

            if actualizar_porcentaje:
                serializer.save(porcentaje_pago=porcentaje)
            else:
                serializer.save()

            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar conductores de otra sucursal.")

            if actualizar_porcentaje and porcentaje is None:
                porcentaje = obtener_configuracion_sucursal(user.sucursal).porcentaje_pago_conductor

            if actualizar_porcentaje:
                serializer.save(sucursal=user.sucursal, porcentaje_pago=porcentaje)
            else:
                serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar conductores.")

    @action(detail=False, methods=["get"], url_path="disponibles-usuario")
    def disponibles_usuario(self, request):
        user = request.user

        qs = Conductor.objects.select_related(
            "sucursal",
            "usuario"
        ).filter(
            usuario__isnull=True,
            activo=True
        ).order_by("nombre", "apellido")

        search = request.query_params.get("search", "").strip()

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            qs = qs.filter(sucursal=user.sucursal)

        elif not es_superadmin(user):
            return Response([])

        if search:
            qs = qs.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(cedula__icontains=search)
            )

        serializer = self.get_serializer(qs.distinct(), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="disponibles")
    def disponibles(self, request):
        # Conductores activos que NO tienen una asignación activa. Sirve para
        # los dropdowns de asignación (solo conductores libres).
        qs = self.get_queryset().filter(activo=True).exclude(
            asignaciones__activa=True
        )

        # Al editar una asignación se debe poder conservar su conductor actual.
        asignacion_id = request.query_params.get("asignacion")
        if asignacion_id:
            actual = AsignacionVehiculo.objects.filter(
                pk=asignacion_id, activa=True
            ).values_list("conductor_id", flat=True).first()
            if actual:
                qs = self.get_queryset().filter(activo=True).filter(
                    Q(pk=actual) | ~Q(asignaciones__activa=True)
                )

        serializer = self.get_serializer(qs.distinct(), many=True)
        return Response(serializer.data)

def despedir(self, request, pk=None):

    @action(detail=True, methods=["post"], url_path="reactivar",
            permission_classes=[EsAdminSucursalOSuperAdmin])
    def reactivar(self, request, pk=None):
        conductor = self.get_object()
        user = request.user

        if es_admin_sucursal(user) and conductor.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes reactivar conductores de otra sucursal.")

        conductor.activo = True
        conductor.save(update_fields=["activo"])

        return Response(
            self.get_serializer(conductor).data,
            status=status.HTTP_200_OK
        )

class VehiculoViewSet(viewsets.ModelViewSet):
    serializer_class = VehiculoSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        documentos_queryset = (
            DocumentoVehiculo.objects
            .select_related(
                "vehiculo"
            )
            .order_by(
                "tipo_documento",
                "-fecha_vencimiento",
                "-id",
            )
        )

        qs = (
            Vehiculo.objects
            .select_related(
                "sucursal",
                "estado",
                "tipo_vehiculo",
            )
            .prefetch_related(
                Prefetch(
                    "documentos",
                    queryset=documentos_queryset,
                    to_attr="documentos_prefetch",
                )
            )
            .all()
            .order_by("placa")
        )

        if es_superadmin(user):
            return qs.filter(
                sucursal__isnull=True
            )

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                return qs.none()

            return qs.filter(
                sucursal_id=user.sucursal_id
            )

        if es_taxista(user):
            return (
                qs.filter(
                    asignaciones__conductor__usuario=user,
                    asignaciones__activa=True,
                )
                .distinct()
            )

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user

        if es_superadmin(user):
            serializer.save(sucursal=None)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear vehículos.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_superadmin(user):
            # El superadmin puede editar cualquier vehículo; se conserva la
            # sucursal actual del vehículo (no se mueve a global).
            serializer.save(sucursal=instance.sucursal)
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar vehículos de otra sucursal.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar vehículos.")

    @action(detail=False, methods=["get"], url_path="disponibles")
    def disponibles(self, request):
        # Vehículos que NO tienen una asignación activa (libres para asignar).
        qs = self.get_queryset().exclude(asignaciones__activa=True)

        # Al editar una asignación se debe poder conservar su vehículo actual.
        asignacion_id = request.query_params.get("asignacion")
        if asignacion_id:
            actual = AsignacionVehiculo.objects.filter(
                pk=asignacion_id, activa=True
            ).values_list("vehiculo_id", flat=True).first()
            if actual:
                qs = self.get_queryset().filter(
                    Q(pk=actual) | ~Q(asignaciones__activa=True)
                )

        serializer = self.get_serializer(qs.distinct(), many=True)
        return Response(serializer.data)

class DocumentoVehiculoViewSet(
    viewsets.ModelViewSet
):
    serializer_class = DocumentoVehiculoSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            return [
                EsAdminSucursalOSuperAdmin()
            ]

        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        qs = (
            DocumentoVehiculo.objects
            .select_related(
                "vehiculo",
                "vehiculo__sucursal",
                "vehiculo__estado",
            )
            .all()
        )

        if es_superadmin(user):
            qs = qs.filter(
                vehiculo__sucursal__isnull=True
            )

        elif es_admin_sucursal(user):
            if not user.sucursal_id:
                return qs.none()

            qs = qs.filter(
                vehiculo__sucursal_id=(
                    user.sucursal_id
                )
            )

        elif es_taxista(user):
            qs = qs.filter(
                vehiculo__asignaciones__conductor__usuario=user,
                vehiculo__asignaciones__activa=True,
            )

        else:
            return qs.none()

        vehiculo_id = (
            self.request.query_params
            .get("vehiculo")
        )

        tipo_documento = (
            self.request.query_params
            .get("tipo_documento")
        )

        estado = (
            self.request.query_params
            .get("estado")
        )

        if vehiculo_id:
            qs = qs.filter(
                vehiculo_id=vehiculo_id
            )

        if tipo_documento:
            tipos_validos = {
                codigo
                for codigo, _nombre
                in (
                    DocumentoVehiculo
                    .TIPO_DOCUMENTO_CHOICES
                )
            }

            if (
                tipo_documento
                not in tipos_validos
            ):
                raise ValidationError({
                    "tipo_documento": (
                        "El tipo de documento "
                        "seleccionado no es válido."
                    )
                })

            qs = qs.filter(
                tipo_documento=tipo_documento
            )

        qs = (
            qs.distinct()
            .order_by(
                "tipo_documento",
                "-fecha_vencimiento",
                "-id",
            )
        )

        if estado:
            estados_validos = {
                "vigente",
                "por_vencer",
                "vencido",
            }

            if estado not in estados_validos:
                raise ValidationError({
                    "estado": (
                        "El estado seleccionado "
                        "no es válido."
                    )
                })

            ids = [
                documento.id
                for documento in qs
                if (
                    documento.estado_documento
                    == estado
                )
            ]

            qs = (
                DocumentoVehiculo.objects
                .select_related(
                    "vehiculo",
                    "vehiculo__sucursal",
                    "vehiculo__estado",
                )
                .filter(
                    id__in=ids
                )
                .order_by(
                    "tipo_documento",
                    "-fecha_vencimiento",
                    "-id",
                )
            )

        return qs

    def _validar_vehiculo(
        self,
        vehiculo,
    ):
        user = self.request.user

        if not vehiculo:
            raise ValidationError({
                "vehiculo": (
                    "Debes seleccionar un vehículo."
                )
            })

        if es_superadmin(user):
            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "Desde el panel del superadministrador "
                    "solo puedes administrar documentos "
                    "de vehículos sin sucursal."
                )

            return

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                raise ValidationError({
                    "sucursal": (
                        "Tu usuario no tiene una "
                        "sucursal asignada."
                    )
                })

            if (
                vehiculo.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes administrar documentos "
                    "de vehículos de otra sucursal."
                )

            return

        raise PermissionDenied(
            "No tienes permiso para administrar "
            "documentos de vehículos."
        )

    def _guardar_validado(
        self,
        serializer,
    ):
        vehiculo = serializer.validated_data.get(
            "vehiculo",
            getattr(
                serializer.instance,
                "vehiculo",
                None,
            ),
        )

        self._validar_vehiculo(
            vehiculo
        )

        instance = (
            serializer.instance
            or DocumentoVehiculo()
        )

        for attr, value in (
            serializer.validated_data.items()
        ):
            setattr(
                instance,
                attr,
                value,
            )

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            if hasattr(
                exc,
                "message_dict",
            ):
                raise ValidationError(
                    exc.message_dict
                )

            raise ValidationError(
                exc.messages
            )

        serializer.save(
            vehiculo=vehiculo
        )

    def perform_create(
        self,
        serializer,
    ):
        self._guardar_validado(
            serializer
        )

   


class AsignacionVehiculoViewSet(viewsets.ModelViewSet):
    serializer_class = AsignacionVehiculoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsAdminSucursalOSuperAdmin()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        qs = (
            AsignacionVehiculo.objects
            .select_related(
                "sucursal",
                "conductor",
                "conductor__sucursal",
                "conductor__usuario",
                "vehiculo",
                "vehiculo__sucursal",
            )
            .all()
            .order_by(
                "-fecha_inicio",
                "-id",
            )
        )

        if es_superadmin(user):
            return qs.filter(
                sucursal__isnull=True
            )

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                return qs.none()

            return qs.filter(
                sucursal_id=user.sucursal_id
            )

        if es_taxista(user):
            return qs.filter(
                conductor__usuario=user
            )

        return qs.none()
    def _guardar_validado(self, serializer, sucursal):
        # Construye la instancia con los datos entrantes y corre full_clean()
        # (que dispara Asignacion.clean) ANTES de guardar. Traduce el error de
        # Django a un 400 con el mensaje claro de la validación.
        instance = serializer.instance or AsignacionVehiculo()
        for attr, value in serializer.validated_data.items():
            setattr(instance, attr, value)
        instance.sucursal = sucursal

        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)

        serializer.save(sucursal=sucursal)

    def perform_create(self, serializer):
        user = self.request.user
        conductor = serializer.validated_data.get("conductor")
        vehiculo = serializer.validated_data.get("vehiculo")

        if es_superadmin(user):
            if conductor.sucursal_id is not None:
                raise PermissionDenied(
                    "Desde el panel del superadministrador "
                    "solo puedes asignar conductores sin sucursal."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "Desde el panel del superadministrador "
                    "solo puedes asignar vehículos sin sucursal."
                )

            self._guardar_validado(
                serializer,
                None
            )

            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar vehículos de otra sucursal.")

            self._guardar_validado(serializer, user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear asignaciones.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        conductor = serializer.validated_data.get("conductor", instance.conductor)
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if es_superadmin(user):
            # El superadmin puede modificar cualquier asignación; conductor y
            # vehículo deben seguir siendo de la misma sucursal.
            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise PermissionDenied(
                    "El conductor y el vehículo deben pertenecer a la misma sucursal."
                )

            self._guardar_validado(serializer, conductor.sucursal)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar asignaciones de otra sucursal.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar vehículos de otra sucursal.")

            self._guardar_validado(serializer, user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar asignaciones.")
    @action(
        detail=True,
        methods=["post"],
        url_path="finalizar",
        permission_classes=[EsAdminSucursalOSuperAdmin]
    )
    def finalizar(self, request, pk=None):
        asignacion = self.get_object()
        user = request.user

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if asignacion.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes finalizar asignaciones de otra sucursal."
                )

        if not asignacion.activa:
            return Response(
                {"detail": "Esta asignación ya está finalizada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        fecha_fin = request.data.get("fecha_fin")

        if fecha_fin:
            fecha_fin = parse_date(str(fecha_fin))

            if not fecha_fin:
                raise ValidationError({
                    "fecha_fin": "La fecha final no tiene un formato válido. Usa YYYY-MM-DD."
                })
        else:
            fecha_fin = timezone.localdate()

        if fecha_fin < asignacion.fecha_inicio:
            raise ValidationError({
                "fecha_fin": "La fecha final no puede ser menor que la fecha de inicio."
            })

        asignacion.activa = False
        asignacion.fecha_fin = fecha_fin
        asignacion.save(update_fields=["activa", "fecha_fin"])

        return Response(
            self.get_serializer(asignacion).data,
            status=status.HTTP_200_OK
        )

class JornadaDiariaViewSet(
    viewsets.ModelViewSet
):
    serializer_class = (
        JornadaDiariaSerializer
    )

    def get_permissions(self):
        if self.action in [
            "update",
            "partial_update",
            "destroy",
            "registrar_ingreso",
        ]:
            return [
                EsAdminSucursalOSuperAdmin()
            ]

        return [
            IsAuthenticated()
        ]

    def get_serializer_context(self):
        context = (
            super()
            .get_serializer_context()
        )

        context["request"] = (
            self.request
        )

        return context

    def get_queryset(self):
        user = self.request.user

        gastos_queryset = (
            Gasto.objects
            .select_related(
                "sucursal",
                "vehiculo",
                "tipo_gasto",
                "estado",
            )
            .order_by("id")
        )

        adelantos_queryset = (
            Adelanto.objects
            .select_related(
                "sucursal",
                "jornada",
                "conductor",
                "estado",
            )
            .order_by("id")
        )

        detalles_liquidacion_queryset = (
            DetalleLiquidacion.objects
            .only(
                "id",
                "jornada_id",
                "liquidacion_id",
            )
            .order_by("id")
        )

        qs = (
            JornadaDiaria.objects
            .select_related(
                "sucursal",
                "estado",
                "conductor",
                "vehiculo",
            )
            .prefetch_related(
                Prefetch(
                    "gastos",
                    queryset=(
                        gastos_queryset
                    ),
                ),
                Prefetch(
                    "adelantos",
                    queryset=(
                        adelantos_queryset
                    ),
                ),
                Prefetch(
                    "detalles_liquidacion",
                    queryset=(
                        detalles_liquidacion_queryset
                    ),
                    to_attr=(
                        "detalles_liquidacion_prefetch"
                    ),
                ),
            )
            .order_by(
                "-fecha",
                "-id",
            )
        )

        fecha = (
            self.request
            .query_params
            .get("fecha")
        )

        fecha_inicio = (
            self.request
            .query_params
            .get("fecha_inicio")
        )

        fecha_fin = (
            self.request
            .query_params
            .get("fecha_fin")
        )

        conductor_id = (
            self.request
            .query_params
            .get("conductor")
        )

        vehiculo_id = (
            self.request
            .query_params
            .get("vehiculo")
        )

        if es_superadmin(user):
            qs = qs.filter(
                sucursal__isnull=True
            )

        elif es_admin_sucursal(user):
            if not user.sucursal_id:
                return qs.none()

            qs = qs.filter(
                sucursal_id=(
                    user.sucursal_id
                )
            )

        elif es_taxista(user):
            qs = qs.filter(
                conductor__usuario=user
            )

        else:
            return qs.none()

        if fecha:
            qs = qs.filter(
                fecha=fecha
            )

        if fecha_inicio:
            qs = qs.filter(
                fecha__gte=fecha_inicio
            )

        if fecha_fin:
            qs = qs.filter(
                fecha__lte=fecha_fin
            )

        if conductor_id:
            qs = qs.filter(
                conductor_id=conductor_id
            )

        if vehiculo_id:
            qs = qs.filter(
                vehiculo_id=vehiculo_id
            )

        return qs

    def _obtener_porcentaje_fallback(
        self,
        sucursal,
    ):
        configuracion = (
            obtener_configuracion_sucursal(
                sucursal
            )
        )

        return (
            configuracion
            .porcentaje_pago_conductor
        )

    def _resolver_porcentaje(
        self,
        conductor,
        sucursal,
    ):
        tipo_cobro = (
            getattr(
                conductor,
                "tipo_cobro",
                "porcentaje",
            )
            or "porcentaje"
        )

        # En alquiler no se usa porcentaje.
        if tipo_cobro == "alquiler":
            return Decimal("0")

        porcentaje = getattr(
            conductor,
            "porcentaje_pago",
            None,
        )

        if porcentaje in [None, ""]:
            porcentaje = (
                self._obtener_porcentaje_fallback(
                    sucursal
                )
            )

        porcentaje = Decimal(str(porcentaje))

        if (
            porcentaje < Decimal("1.00")
            or porcentaje > Decimal("100.00")
        ):
            raise ValidationError({
                "porcentaje_pago": (
                    "El porcentaje del conductor debe "
                    "estar entre 1 y 100."
                )
            })

        return porcentaje.quantize(
            Decimal("0.01")
        )

    def _obtener_detalle_liquidacion(
        self,
        jornada,
    ):
        detalles_precargados = getattr(
            jornada,
            "detalles_liquidacion_prefetch",
            None,
        )

        if detalles_precargados is not None:
            return (
                detalles_precargados[0]
                if detalles_precargados
                else None
            )

        return (
            jornada.detalles_liquidacion
            .only(
                "id",
                "jornada_id",
                "liquidacion_id",
            )
            .order_by("id")
            .first()
        )

    def _validar_jornada_no_liquidada(
        self,
        jornada,
    ):
        detalle = (
            self._obtener_detalle_liquidacion(
                jornada
            )
        )

        if detalle:
            raise ValidationError({
                "detail": (
                    "Esta jornada ya fue incluida en la "
                    f"liquidación #{detalle.liquidacion_id} "
                    "y no puede modificarse."
                )
            })

    def _obtener_estado_jornada(
        self,
        codigo,
        nombre,
    ):
        estado, _ = (
            EstadoJornada.objects
            .get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "activo": True,
                },
            )
        )

        campos_actualizados = []

        if estado.nombre != nombre:
            estado.nombre = nombre

            campos_actualizados.append(
                "nombre"
            )

        if not estado.activo:
            estado.activo = True

            campos_actualizados.append(
                "activo"
            )

        if campos_actualizados:
            estado.save(
                update_fields=(
                    campos_actualizados
                )
            )

        return estado

    def _obtener_estado_vehiculo(
        self,
        codigo,
        nombre,
    ):
        estado, _ = (
            EstadoVehiculo.objects
            .get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "activo": True,
                },
            )
        )

        campos_actualizados = []

        if estado.nombre != nombre:
            estado.nombre = nombre

            campos_actualizados.append(
                "nombre"
            )

        if not estado.activo:
            estado.activo = True

            campos_actualizados.append(
                "activo"
            )

        if campos_actualizados:
            estado.save(
                update_fields=(
                    campos_actualizados
                )
            )

        return estado

    def perform_create(
        self,
        serializer,
    ):
        user = self.request.user

        conductor = (
            serializer
            .validated_data
            .get("conductor")
        )

        vehiculo = (
            serializer
            .validated_data
            .get("vehiculo")
        )

        if es_taxista(user):
            try:
                conductor = (
                    user.perfil_conductor
                )

            except Conductor.DoesNotExist:
                raise ValidationError(
                    "Este usuario no tiene perfil de conductor."
                )

        if not conductor:
            raise ValidationError(
                "Debes indicar el conductor."
            )

        if not vehiculo:
            raise ValidationError(
                "Debes indicar el vehículo."
            )

        if es_superadmin(user):
            if (
                conductor.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes registrar jornadas de "
                    "conductores de sucursal desde el "
                    "panel superadmin."
                )

            if (
                vehiculo.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes registrar jornadas de "
                    "vehículos de sucursal desde el "
                    "panel superadmin."
                )

            sucursal = None

        elif es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError(
                    "Tu usuario no tiene una sucursal asignada."
                )

            if (
                conductor.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes registrar jornadas para "
                    "conductores de otra sucursal."
                )

            if (
                vehiculo.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes registrar jornadas para "
                    "vehículos de otra sucursal."
                )

            sucursal = user.sucursal

        elif es_taxista(user):
            if (
                conductor.usuario_id
                != user.id
            ):
                raise PermissionDenied(
                    "No puedes crear jornadas para otro conductor."
                )

            if (
                conductor.sucursal_id
                != vehiculo.sucursal_id
            ):
                raise ValidationError(
                    "El conductor y el vehículo deben "
                    "pertenecer al mismo entorno."
                )

            sucursal = (
                conductor.sucursal
            )

        else:
            raise PermissionDenied(
                "No tienes permiso para crear jornadas."
            )

        asignacion_activa = (
            AsignacionVehiculo.objects
            .filter(
                sucursal=sucursal,
                conductor=conductor,
                vehiculo=vehiculo,
                activa=True,
            )
            .exists()
        )

        if not asignacion_activa:
            raise ValidationError(
                "El conductor no tiene una asignación "
                "activa con ese vehículo."
            )

        fecha = (
            serializer
            .validated_data
            .get(
                "fecha",
                timezone.localdate(),
            )
        )

        jornada_existente = (
            JornadaDiaria.objects
            .filter(
                fecha=fecha,
                conductor=conductor,
                vehiculo=vehiculo,
            )
            .exists()
        )

        if jornada_existente:
            raise ValidationError({
                "detail": (
                    "Ya existe una jornada para este "
                    "conductor y vehículo en esta fecha. "
                    "Debes cerrar la jornada existente, "
                    "no crear otra."
                )
            })

        porcentaje = (
            self._resolver_porcentaje(
                conductor,
                sucursal,
            )
        )

        estado_jornada_circulando = (
            self._obtener_estado_jornada(
                codigo="circulando",
                nombre="Circulando",
            )
        )

        estado_vehiculo_circulando = (
            self._obtener_estado_vehiculo(
                codigo="circulando",
                nombre="Circulando",
            )
            )
        tipo_cobro = (
            getattr(
                conductor,
                "tipo_cobro",
                "porcentaje",
            )
            or "porcentaje"
        )

        porcentaje_pago = (
            Decimal("0.00")
            if tipo_cobro == "alquiler"
            else porcentaje
            )       

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            estado=(estado_jornada_circulando),
            kilometraje_final=None,
            kilometros_recorridos=0,
            ingreso_bruto=Decimal("0.00"),
            monto_alquiler=Decimal("0.00"),
            tipo_cobro=tipo_cobro,
            porcentaje_pago_conductor=(
            porcentaje_pago),
            pago_conductor=Decimal("0.00"),
        )

        vehiculo.estado = (
            estado_vehiculo_circulando
        )

        vehiculo.save(
            update_fields=[
                "estado",
            ]
        )

        recalcular_totales_jornada(
            jornada
        )

    def perform_update(
        self,
        serializer,
    ):
        user = self.request.user

        instance = self.get_object()

        self._validar_jornada_no_liquidada(
            instance
        )

        conductor = (
            serializer
            .validated_data
            .get(
                "conductor",
                instance.conductor,
            )
        )

        vehiculo = (
            serializer
            .validated_data
            .get(
                "vehiculo",
                instance.vehiculo,
            )
        )

        if es_superadmin(user):
            if (
                instance.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes modificar jornadas de "
                    "sucursal desde el panel superadmin."
                )

            if (
                conductor.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes usar conductores de sucursal "
                    "desde el panel superadmin."
                )

            if (
                vehiculo.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes usar vehículos de sucursal "
                    "desde el panel superadmin."
                )

            sucursal = None

        elif es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError(
                    "Tu usuario no tiene una sucursal asignada."
                )

            if (
                instance.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes modificar jornadas de otra sucursal."
                )

            if (
                conductor.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes usar conductores de otra sucursal."
                )

            if (
                vehiculo.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes usar vehículos de otra sucursal."
                )

            sucursal = user.sucursal

        elif es_taxista(user):
            if (
                instance.conductor.usuario_id
                != user.id
            ):
                raise PermissionDenied(
                    "No puedes modificar jornadas de otro conductor."
                )

            if (
                conductor.usuario_id
                != user.id
            ):
                raise PermissionDenied(
                    "No puedes cambiar la jornada a otro conductor."
                )

            if (
                conductor.sucursal_id
                != vehiculo.sucursal_id
            ):
                raise ValidationError(
                    "El conductor y el vehículo deben "
                    "pertenecer al mismo entorno."
                )

            sucursal = (
                conductor.sucursal
            )

        else:
            raise PermissionDenied(
                "No tienes permiso para modificar jornadas."
            )

        asignacion_activa = (
            AsignacionVehiculo.objects
            .filter(
                sucursal=sucursal,
                conductor=conductor,
                vehiculo=vehiculo,
                activa=True,
            )
            .exists()
        )

        if not asignacion_activa:
            raise ValidationError(
                "El conductor no tiene una asignación "
                "activa con ese vehículo."
            )

        porcentaje = (
            self._resolver_porcentaje(
                conductor,
                sucursal,
            )
        )

        tipo_cobro = (
            getattr(
                conductor,
                "tipo_cobro",
                "porcentaje",
            )
            or "porcentaje"
        )

        porcentaje_pago = (
            Decimal("0.00")
            if tipo_cobro == "alquiler"
            else porcentaje
        )

        km_inicial = (
            serializer
            .validated_data
            .get(
                "kilometraje_inicial",
                instance.kilometraje_inicial,
            )
        )

        km_final = (
            serializer
            .validated_data
            .get(
                "kilometraje_final",
                instance.kilometraje_final,
            )
        )

        ingreso_bruto = (
            serializer
            .validated_data
            .get(
                "ingreso_bruto",
                instance.ingreso_bruto,
            )
        )

        tipo_cobro = (
            getattr(
                conductor,
                "tipo_cobro",
                instance.tipo_cobro,
            )
            or "porcentaje"
        )

        monto_alquiler = (
            serializer
            .validated_data
            .get(
                "monto_alquiler",
                instance.monto_alquiler,
            )
        )

        campos_calculados = (
            calcular_campos_jornada(
                km_inicial,
                km_final,
                ingreso_bruto,
                porcentaje,
                tipo_cobro,
                monto_alquiler,
            )
        )

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            porcentaje_pago_conductor=(
                porcentaje
            ),
            kilometros_recorridos=(
                campos_calculados[
                    "kilometros_recorridos"
                ]
            ),
            pago_conductor=(
                campos_calculados[
                    "pago_conductor"
                ]
            ),
        )

        actualizar_kilometraje_vehiculo(
            vehiculo,
            jornada.kilometraje_final,
        )

        recalcular_totales_jornada(
            jornada
        )

    def perform_destroy(
        self,
        instance,
    ):
        self._validar_jornada_no_liquidada(
            instance
        )

        instance.delete()

    @action(
        detail=True,
        methods=["patch"],
        url_path="cerrar",
    )
    def cerrar(
        self,
        request,
        pk=None,
    ):
        jornada = self.get_object()
        user = request.user

        kilometraje_final = (
            request.data.get(
                "kilometraje_final"
            )
        )

        tipo_cobro = str(
            jornada.tipo_cobro or "porcentaje"
        ).strip().lower()

        if es_taxista(user):
            if tipo_cobro == "porcentaje":
                ingreso_bruto = request.data.get(
                    "ingreso_bruto"
                )

                if ingreso_bruto in [None, ""]:
                    raise ValidationError({
                        "ingreso_bruto": (
                            "Debes ingresar el total producido del día."
                        )
                    })

                try:
                    ingreso_bruto = Decimal(
                        str(ingreso_bruto)
                    )
                except (
                    TypeError,
                    ValueError,
                    InvalidOperation,
                ):
                    raise ValidationError({
                        "ingreso_bruto": (
                            "El total producido del día debe ser válido."
                        )
                    })

                if ingreso_bruto < 0:
                    raise ValidationError({
                        "ingreso_bruto": (
                            "El total producido del día no puede ser negativo."
                        )
                    })
            else:
                # En alquiler el taxista solo registra kilometraje.
                ingreso_bruto = jornada.ingreso_bruto

        else:
            ingreso_bruto = request.data.get(
                "ingreso_bruto",
                jornada.ingreso_bruto,
            )

        try:
            ingreso_bruto = Decimal(
                str(ingreso_bruto or 0)
            )
        except (
            TypeError,
            ValueError,
            InvalidOperation,
        ):
            raise ValidationError({
                "ingreso_bruto": (
                    "El ingreso bruto debe ser válido."
                )
            })

        if kilometraje_final in [
            None,
            "",
        ]:
            raise ValidationError({
                "kilometraje_final": (
                    "Debes ingresar el kilometraje final."
                )
            })

        try:
            kilometraje_final = int(
                kilometraje_final
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValidationError({
                "kilometraje_final": (
                    "El kilometraje final debe ser "
                    "un número válido."
                )
            })

        if (
            jornada.kilometraje_final
            is not None
        ):
            raise ValidationError({
                "detail": (
                    "Esta jornada ya fue cerrada."
                )
            })

        if (
            kilometraje_final
            < jornada.kilometraje_inicial
        ):
            raise ValidationError({
                "kilometraje_final": (
                    "El kilometraje final no puede ser "
                    "menor al kilometraje inicial."
                )
            })

        if es_taxista(user):
            if (
                jornada.conductor.usuario_id
                != user.id
            ):
                raise PermissionDenied(
                    "No puedes cerrar una jornada "
                    "de otro conductor."
                )

        elif es_admin_sucursal(user):
            if (
                jornada.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes cerrar jornadas "
                    "de otra sucursal."
                )

        elif es_superadmin(user):
            if (
                jornada.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes cerrar jornadas de una "
                    "sucursal desde el panel superadmin."
                )

        else:
            raise PermissionDenied(
                "No tienes permiso para cerrar esta jornada."
            )

        porcentaje = (
            self._resolver_porcentaje(
                jornada.conductor,
                jornada.sucursal,
            )
        )

        campos_calculados = (
            calcular_campos_jornada(
                jornada.kilometraje_inicial,
                kilometraje_final,
                ingreso_bruto,
                porcentaje,
                jornada.tipo_cobro,
                jornada.monto_alquiler,
            )
        )

        estado_jornada_parqueado = (
            self._obtener_estado_jornada(
                codigo="parqueado",
                nombre="Parqueado",
            )
        )

        estado_vehiculo_parqueado = (
            self._obtener_estado_vehiculo(
                codigo="parqueado",
                nombre="Parqueado",
            )
        )

        jornada.kilometraje_final = (
            kilometraje_final
        )

        jornada.ingreso_bruto = (
            ingreso_bruto
        )

        jornada.porcentaje_pago_conductor = (
            porcentaje
        )

        jornada.estado = (
            estado_jornada_parqueado
        )

        jornada.kilometros_recorridos = (
            campos_calculados[
                "kilometros_recorridos"
            ]
        )

        jornada.pago_conductor = (
            campos_calculados[
                "pago_conductor"
            ]
        )

        if (
            request.data.get(
                "observaciones"
            )
            is not None
        ):
            jornada.observaciones = (
                request.data.get(
                    "observaciones"
                )
            )

        jornada.save(
            update_fields=[
                "kilometraje_final",
                "ingreso_bruto",
                "porcentaje_pago_conductor",
                "estado",
                "kilometros_recorridos",
                "pago_conductor",
                "observaciones",
            ]
        )

        jornada.vehiculo.estado = (
            estado_vehiculo_parqueado
        )

        jornada.vehiculo.save(
            update_fields=[
                "estado",
            ]
        )

        actualizar_kilometraje_vehiculo(
            jornada.vehiculo,
            jornada.kilometraje_final,
        )

        recalcular_totales_jornada(
            jornada
        )

        serializer = (
            self.get_serializer(
                jornada
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="registrar-ingreso",
        permission_classes=[
            EsAdminSucursalOSuperAdmin
        ],
    )
    def registrar_ingreso(
        self,
        request,
        pk=None,
    ):
        jornada = self.get_object()
        user = request.user

        self._validar_jornada_no_liquidada(
            jornada
        )

        if (
            not es_superadmin(user)
            and not es_admin_sucursal(user)
        ):
            raise PermissionDenied(
                "Solo administración puede registrar "
                "el ingreso del día."
            )

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError(
                    "Tu usuario no tiene una sucursal asignada."
                )

            if (
                jornada.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes registrar ingresos "
                    "de otra sucursal."
                )

        if es_superadmin(user):
            if (
                jornada.sucursal_id
                is not None
            ):
                raise PermissionDenied(
                    "No puedes registrar ingresos de una "
                    "sucursal desde el panel superadmin."
                )

            tipo_cobro = (
            getattr(
                jornada.conductor,
                "tipo_cobro",
                jornada.tipo_cobro,
            )
            or "porcentaje"
        )

        if tipo_cobro not in [
            "porcentaje",
            "alquiler",
        ]:
            raise ValidationError({
                "tipo_cobro": (
                    "El tipo de cobro debe ser "
                    "porcentaje o alquiler."
                )
            })

        ingreso_bruto = _decimal(
            request.data.get(
                "ingreso_bruto"
            )
        )

        monto_alquiler = _decimal(
            request.data.get(
                "monto_alquiler"
            )
        )

        porcentaje = (
            self._resolver_porcentaje(
                jornada.conductor,
                jornada.sucursal,
            )
        )

        if tipo_cobro == "porcentaje":
            if ingreso_bruto < 0:
                raise ValidationError({
                    "ingreso_bruto": (
                        "El ingreso del día no puede ser negativo."
                    )
                })

            jornada.ingreso_bruto = (
                ingreso_bruto
            )

            jornada.monto_alquiler = (
                Decimal("0.00")
            )

            jornada.porcentaje_pago_conductor = (
                porcentaje
            )

        elif tipo_cobro == "alquiler":
            if monto_alquiler < 0:
                raise ValidationError({
                    "monto_alquiler": (
                        "El monto de alquiler no "
                        "puede ser negativo."
                    )
                })

            jornada.ingreso_bruto = (
                monto_alquiler
            )

            jornada.monto_alquiler = (
                monto_alquiler
            )

            jornada.porcentaje_pago_conductor = (
                Decimal("0.00")
            )

        jornada.tipo_cobro = (
            tipo_cobro
        )

        if (
            request.data.get(
                "observaciones"
            )
            is not None
        ):
            jornada.observaciones = (
                request.data.get(
                    "observaciones"
                )
            )

        campos_calculados = (
            calcular_campos_jornada(
                jornada.kilometraje_inicial,
                jornada.kilometraje_final,
                jornada.ingreso_bruto,
                jornada.porcentaje_pago_conductor,
                jornada.tipo_cobro,
                jornada.monto_alquiler,
            )
        )

        jornada.kilometros_recorridos = (
            campos_calculados[
                "kilometros_recorridos"
            ]
        )

        jornada.pago_conductor = (
            campos_calculados[
                "pago_conductor"
            ]
        )

        jornada.ingreso_bruto = (
            campos_calculados[
                "ingreso_bruto"
            ]
        )

        jornada.save(
            update_fields=[
                "tipo_cobro",
                "ingreso_bruto",
                "monto_alquiler",
                "porcentaje_pago_conductor",
                "kilometros_recorridos",
                "pago_conductor",
                "observaciones",
            ]
        )

        recalcular_totales_jornada(
            jornada
        )

        serializer = (
            self.get_serializer(
                jornada
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

class GastoViewSet(viewsets.ModelViewSet):
    serializer_class = GastoSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]

        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        qs = Gasto.objects.select_related(
            "sucursal",
            "vehiculo",
            "tipo_gasto",
            "estado"
        ).all()

        fecha = self.request.query_params.get("fecha")
        fecha_inicio = self.request.query_params.get("fecha_inicio")
        fecha_fin = self.request.query_params.get("fecha_fin")
        vehiculo_id = self.request.query_params.get("vehiculo")

        if es_superadmin(user):
            qs = qs.filter(sucursal__isnull=True)

        elif es_admin_sucursal(user):
            qs = qs.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            return qs.none()

        else:
            return qs.none()

        if fecha:
            qs = qs.filter(fecha=fecha)

        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)

        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)

        if vehiculo_id:
            qs = qs.filter(vehiculo_id=vehiculo_id)

        return qs.order_by("-fecha", "-id")

    def perform_create(self, serializer):
        user = self.request.user
        vehiculo = serializer.validated_data.get("vehiculo")

        if not vehiculo:
            raise ValidationError("Debes indicar el vehículo.")

        if es_superadmin(user):
            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes registrar gastos de vehículos de una sucursal desde el panel superadmin."
                )

            serializer.save(
                sucursal=None,
                vehiculo=vehiculo,
                jornada=None,
                conductor=None
            )
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes registrar gastos para vehículos de otra sucursal."
                )

            serializer.save(
                sucursal=user.sucursal,
                vehiculo=vehiculo,
                jornada=None,
                conductor=None
            )
            return

        raise PermissionDenied("No tienes permiso para registrar gastos.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if not vehiculo:
            raise ValidationError("Debes indicar el vehículo.")

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes modificar gastos de una sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes mover este gasto a un vehículo de sucursal."
                )

            serializer.save(
                sucursal=None,
                vehiculo=vehiculo,
                jornada=None,
                conductor=None
            )
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar gastos de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes asignar gastos a vehículos de otra sucursal."
                )

            serializer.save(
                sucursal=user.sucursal,
                vehiculo=vehiculo,
                jornada=None,
                conductor=None
            )
            return

        raise PermissionDenied("No tienes permiso para modificar gastos.")

    def perform_destroy(self, instance):
        user = self.request.user

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes eliminar gastos de una sucursal desde el panel superadmin."
                )

        elif es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes eliminar gastos de otra sucursal.")

        else:
            raise PermissionDenied("No tienes permiso para eliminar gastos.")

        instance.delete()


class AdelantoViewSet(viewsets.ModelViewSet):
    serializer_class = AdelantoSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Adelanto.objects.select_related(
            "sucursal",
            "jornada",
            "conductor",
            "estado"
        ).all()

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(sucursal=user.sucursal, conductor__usuario=user)

        return qs.none()

    @action(
    detail=False,
    methods=["get"],
    url_path="resumen-conductores",
    )
    def resumen_conductores(
                self,
            request,
        ):
            """
            Devuelve una sola fila por conductor con:

            - Total de adelantos.
            - Total de abonos.
            - Saldo pendiente.
            - Cantidad de movimientos.
            - Fecha del último movimiento.

            Los movimientos originales no se eliminan ni se combinan.
            """

            qs = (
                self.get_queryset()
                .filter(
                    conductor__isnull=False
                )
            )

            conductor_id = (
                request.query_params.get(
                    "conductor"
                )
            )

            estado_saldo = str(
                request.query_params.get(
                    "estado_saldo",
                    "todos",
                )
            ).strip().lower()

            if conductor_id:
                qs = qs.filter(
                    conductor_id=conductor_id
                )

            filtro_abonos = Q(
                estado__codigo__in=[
                    "abono",
                    "abonado",
                ]
            )

            filtro_adelantos = (
                Q(
                    estado__codigo__in=[
                        "adelanto",
                        "anticipo",
                    ]
                )
                |
                Q(
                    estado__codigo__isnull=True
                )
            )

            campo_dinero = DecimalField(
                max_digits=14,
                decimal_places=2,
            )

            resumen = (
                qs.values(
                    "conductor_id",
                    "conductor__nombre",
                    "conductor__apellido",
                    "conductor__cedula",
                    "conductor__sucursal_id",
                    "conductor__sucursal__nombre",
                )
                .annotate(
                    total_adelantos=Coalesce(
                        Sum(
                            "monto",
                            filter=filtro_adelantos,
                        ),
                        Value(
                            Decimal("0.00")
                        ),
                        output_field=campo_dinero,
                    ),

                    total_abonos=Coalesce(
                        Sum(
                            "monto",
                            filter=filtro_abonos,
                        ),
                        Value(
                            Decimal("0.00")
                        ),
                        output_field=campo_dinero,
                    ),

                    cantidad_adelantos=Count(
                        "id",
                        filter=filtro_adelantos,
                    ),

                    cantidad_abonos=Count(
                        "id",
                        filter=filtro_abonos,
                    ),

                    cantidad_movimientos=Count(
                        "id"
                    ),

                    ultimo_movimiento=Max(
                        "fecha"
                    ),
                )
            )

            resultado = []

            for item in resumen:
                total_adelantos = Decimal(
                    item.get(
                        "total_adelantos"
                    )
                    or "0.00"
                ).quantize(
                    Decimal("0.01")
                )

                total_abonos = Decimal(
                    item.get(
                        "total_abonos"
                    )
                    or "0.00"
                ).quantize(
                    Decimal("0.01")
                )

                saldo_calculado = (
                    total_adelantos
                    - total_abonos
                ).quantize(
                    Decimal("0.01")
                )

                saldo_pendiente = max(
                    saldo_calculado,
                    Decimal("0.00"),
                )

                saldo_a_favor = max(
                    -saldo_calculado,
                    Decimal("0.00"),
                )

                if (
                    estado_saldo
                    in {
                        "pendiente",
                        "con_saldo",
                    }
                    and saldo_pendiente
                    <= Decimal("0.00")
                ):
                    continue

                if (
                    estado_saldo
                    in {
                        "cancelado",
                        "cancelados",
                        "sin_saldo",
                    }
                    and saldo_pendiente
                    > Decimal("0.00")
                ):
                    continue

                nombre = (
                    f"{item.get('conductor__nombre') or ''} "
                    f"{item.get('conductor__apellido') or ''}"
                ).strip()

                resultado.append({
                    "conductor_id":
                        item["conductor_id"],

                    "conductor_nombre":
                        nombre,

                    "conductor_cedula":
                        item.get(
                            "conductor__cedula"
                        )
                        or "",

                    "sucursal_id":
                        item.get(
                            "conductor__sucursal_id"
                        ),

                    "sucursal_nombre":
                        item.get(
                            "conductor__sucursal__nombre"
                        )
                        or "Sin sucursal",

                    "total_adelantos":
                        str(total_adelantos),

                    "total_abonos":
                        str(total_abonos),

                    "saldo_pendiente":
                        str(saldo_pendiente),

                    "saldo_a_favor":
                        str(saldo_a_favor),

                    "cantidad_adelantos":
                        item.get(
                            "cantidad_adelantos"
                        )
                        or 0,

                    "cantidad_abonos":
                        item.get(
                            "cantidad_abonos"
                        )
                        or 0,

                    "cantidad_movimientos":
                        item.get(
                            "cantidad_movimientos"
                        )
                        or 0,

                    "ultimo_movimiento":
                        item.get(
                            "ultimo_movimiento"
                        ),

                    "tiene_saldo":
                        saldo_pendiente
                        > Decimal("0.00"),
                })

            resultado.sort(
                key=lambda item: (
                    -Decimal(
                        item[
                            "saldo_pendiente"
                        ]
                    ),
                    item[
                        "conductor_nombre"
                    ].lower(),
                )
            )

            return Response({
                "count": len(resultado),
                "results": resultado,
            })

    def _resolver_estado(self, tipo, estado_actual=None):
        tipo_limpio = str(tipo or "").strip().upper()

        if not tipo_limpio:
            if estado_actual:
                return estado_actual

            tipo_limpio = "ADELANTO"

        tipos_validos = {
            "ADELANTO": ("adelanto", "Adelanto"),
            "ANTICIPO": ("adelanto", "Adelanto"),
            "ABONO": ("abono", "Abono"),
        }

        if tipo_limpio not in tipos_validos:
            raise ValidationError({
                "tipo": "Tipo de movimiento inválido. Usa ADELANTO o ABONO."
            })

        codigo, nombre = tipos_validos[tipo_limpio]

        estado, _ = EstadoAdelanto.objects.get_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "activo": True,
            }
        )

        return estado

    def _resolver_sucursal_conductor(self, jornada, conductor):
        # Si el movimiento va ligado a una jornada, manda la jornada; si no,
        # el ámbito (sucursal) se hereda del conductor (None para el superadmin).
        if jornada:
            return jornada.sucursal, jornada.conductor
        return conductor.sucursal, conductor

    def perform_create(self, serializer):
        user = self.request.user
        tipo = serializer.validated_data.pop("tipo", None)
        jornada = serializer.validated_data.get("jornada")
        conductor = serializer.validated_data.get("conductor")

        if not jornada and not conductor:
            raise ValidationError("Debes indicar el conductor del movimiento.")

        sucursal, conductor = self._resolver_sucursal_conductor(jornada, conductor)

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")
            if sucursal is None or sucursal.id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar adelantos en otra sucursal.")
        # El superadmin puede registrar movimientos de cualquier conductor; la
        # sucursal se hereda del conductor (o de la jornada).

        estado = self._resolver_estado(
            tipo, serializer.validated_data.get("estado")
        )

        adelanto = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            estado=estado,
        )

        if adelanto.jornada:
            recalcular_totales_jornada(adelanto.jornada)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        tipo = serializer.validated_data.pop("tipo", None)

        jornada = serializer.validated_data.get("jornada", instance.jornada)
        conductor = serializer.validated_data.get("conductor", instance.conductor)

        sucursal, conductor = self._resolver_sucursal_conductor(jornada, conductor)

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar adelantos de otra sucursal.")
            if sucursal is None or sucursal.id != user.sucursal_id:
                raise PermissionDenied("No puedes mover adelantos a otra sucursal.")
        # El superadmin puede modificar movimientos de cualquier conductor.

        estado = self._resolver_estado(tipo, instance.estado)

        adelanto = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            estado=estado,
        )

        # Recalcula la(s) jornada(s) afectada(s), solo si existen.
        jornada_anterior = instance.jornada
        if jornada_anterior:
            recalcular_totales_jornada(jornada_anterior)
        if adelanto.jornada and adelanto.jornada_id != getattr(jornada_anterior, "id", None):
            recalcular_totales_jornada(adelanto.jornada)

    def perform_destroy(self, instance):
        jornada = instance.jornada
        instance.delete()
        if jornada:
            recalcular_totales_jornada(jornada)


class MantenimientoViewSet(viewsets.ModelViewSet):
    serializer_class = MantenimientoSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            return [
                EsAdminSucursalOSuperAdmin()
            ]

        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        queryset = (
            Mantenimiento.objects
            .select_related(
                "sucursal",
                "vehiculo",
                "tipo_mantenimiento",
                "estado",
            )
            .all()
        )

        fecha = self.request.query_params.get(
            "fecha"
        )

        fecha_inicio = (
            self.request.query_params.get(
                "fecha_inicio"
            )
        )

        fecha_fin = (
            self.request.query_params.get(
                "fecha_fin"
            )
        )

        vehiculo_id = (
            self.request.query_params.get(
                "vehiculo"
            )
        )

        sucursal_id = (
            self.request.query_params.get(
                "sucursal"
            )
        )

        if es_superadmin(user):
            # El superadministrador ve todos los
            # mantenimientos, incluyendo los de sucursales.
            if sucursal_id:
                queryset = queryset.filter(
                    sucursal_id=sucursal_id
                )

        elif es_admin_sucursal(user):
            if not user.sucursal_id:
                return queryset.none()

            queryset = queryset.filter(
                sucursal_id=user.sucursal_id
            )

        elif es_taxista(user):
            return queryset.none()

        else:
            return queryset.none()

        if fecha:
            queryset = queryset.filter(
                fecha=fecha
            )

        if fecha_inicio:
            queryset = queryset.filter(
                fecha__gte=fecha_inicio
            )

        if fecha_fin:
            queryset = queryset.filter(
                fecha__lte=fecha_fin
            )

        if vehiculo_id:
            queryset = queryset.filter(
                vehiculo_id=vehiculo_id
            )

        return queryset.order_by(
            "-fecha",
            "-id",
        )

    def _resolver_sucursal(
        self,
        *,
        user,
        vehiculo,
    ):
        if es_superadmin(user):
            # El mantenimiento hereda la sucursal
            # del vehículo seleccionado.
            return vehiculo.sucursal

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                raise ValidationError({
                    "sucursal": (
                        "Tu usuario no tiene una "
                        "sucursal asignada."
                    )
                })

            if (
                vehiculo.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes registrar mantenimiento "
                    "para vehículos de otra sucursal."
                )

            return user.sucursal

        raise PermissionDenied(
            "No tienes permiso para registrar "
            "mantenimientos."
        )

    def _obtener_intervalo_km(
        self,
        *,
        sucursal,
        tipo_mantenimiento,
    ):
        configuracion = (
            obtener_configuracion_sucursal(
                sucursal
            )
        )

        codigo = str(
            getattr(
                tipo_mantenimiento,
                "codigo",
                "",
            )
            or ""
        ).strip().lower()

        intervalo_tipo = int(
            getattr(
                tipo_mantenimiento,
                "intervalo_km",
                0,
            )
            or 0
        )

        if codigo == "aceite":
            intervalo = int(
                configuracion
                .intervalo_cambio_aceite_km
                or intervalo_tipo
                or 5000
            )
        else:
            intervalo = int(
                configuracion
                .intervalo_mantenimiento_km
                or intervalo_tipo
                or 5000
            )

        if intervalo <= 0:
            raise ValidationError({
                "tipo_mantenimiento": (
                    "El intervalo de mantenimiento "
                    "debe ser mayor que cero."
                )
            })

        return intervalo

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user

        vehiculo = (
            serializer.validated_data.get(
                "vehiculo"
            )
        )

        tipo_mantenimiento = (
            serializer.validated_data.get(
                "tipo_mantenimiento"
            )
        )

        if not vehiculo:
            raise ValidationError({
                "vehiculo": (
                    "Debes seleccionar el vehículo."
                )
            })

        if not tipo_mantenimiento:
            raise ValidationError({
                "tipo_mantenimiento": (
                    "Debes seleccionar el tipo "
                    "de mantenimiento."
                )
            })

        sucursal = self._resolver_sucursal(
            user=user,
            vehiculo=vehiculo,
        )

        intervalo_km = (
            self._obtener_intervalo_km(
                sucursal=sucursal,
                tipo_mantenimiento=(
                    tipo_mantenimiento
                ),
            )
        )

        kilometraje_actual = int(
            vehiculo.kilometraje_actual
            or 0
        )

        proximo_km_sugerido = (
            kilometraje_actual
            + intervalo_km
        )

        mantenimiento = serializer.save(
            sucursal=sucursal,
            vehiculo=vehiculo,
            kilometraje=kilometraje_actual,
            proximo_km_sugerido=(
                proximo_km_sugerido
            ),
        )

        aplicar_mantenimiento_en_vehiculo(
            mantenimiento
        )

    @transaction.atomic
    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        vehiculo_enviado = (
            serializer.validated_data.get(
                "vehiculo",
                instance.vehiculo,
            )
        )

        tipo_enviado = (
            serializer.validated_data.get(
                "tipo_mantenimiento",
                instance.tipo_mantenimiento,
            )
        )

        if (
            vehiculo_enviado.id
            != instance.vehiculo_id
        ):
            raise ValidationError({
                "vehiculo": (
                    "No se puede cambiar el vehículo "
                    "de un mantenimiento ya registrado."
                )
            })

        if (
            tipo_enviado.id
            != instance.tipo_mantenimiento_id
        ):
            raise ValidationError({
                "tipo_mantenimiento": (
                    "No se puede cambiar el tipo "
                    "de un mantenimiento ya registrado."
                )
            })

        sucursal = self._resolver_sucursal(
            user=user,
            vehiculo=instance.vehiculo,
        )

        serializer.save(
            sucursal=sucursal,
            vehiculo=instance.vehiculo,
            tipo_mantenimiento=(
                instance.tipo_mantenimiento
            ),
            kilometraje=instance.kilometraje,
            proximo_km_sugerido=(
                instance.proximo_km_sugerido
            ),
        )

    def perform_destroy(self, instance):
        user = self.request.user

        if es_admin_sucursal(user):
            if not user.sucursal_id:
                raise ValidationError({
                    "sucursal": (
                        "Tu usuario no tiene una "
                        "sucursal asignada."
                    )
                })

            if (
                instance.sucursal_id
                != user.sucursal_id
            ):
                raise PermissionDenied(
                    "No puedes eliminar mantenimiento "
                    "de otra sucursal."
                )

        elif not es_superadmin(user):
            raise PermissionDenied(
                "No tienes permiso para eliminar "
                "mantenimientos."
            )

        instance.delete()


class ConfiguracionSistemaView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [EsAdminSucursalOSuperAdmin()]

    def get_configuracion(self, user):
        if es_superadmin(user):
            configuracion, _ = ConfiguracionSistema.objects.get_or_create(
                sucursal=None
            )
            return configuracion

        if es_admin_sucursal(user):
            if not user.sucursal:
                return None

            configuracion, _ = ConfiguracionSistema.objects.get_or_create(
                sucursal=user.sucursal
            )
            return configuracion

        if es_taxista(user):
            if not user.sucursal:
                return ConfiguracionSistema.objects.filter(
                    sucursal=None
                ).first()

            configuracion = ConfiguracionSistema.objects.filter(
                sucursal=user.sucursal
            ).first()

            if configuracion:
                return configuracion

            return ConfiguracionSistema.objects.filter(
                sucursal=None
            ).first()

        return None

    def get(self, request):
        configuracion = self.get_configuracion(request.user)

        if not configuracion:
            return Response(
                {"detail": "No se encontró configuración para este usuario."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ConfiguracionSistemaSerializer(configuracion)
        return Response(serializer.data)

    def put(self, request):
        if es_taxista(request.user):
            return Response(
                {"detail": "No tienes permiso para modificar la configuración."},
                status=status.HTTP_403_FORBIDDEN
            )

        configuracion = self.get_configuracion(request.user)

        if not configuracion:
            return Response(
                {"detail": "No se encontró configuración para este usuario."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ConfiguracionSistemaSerializer(
            configuracion,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        return self.put(request)


class DashboardResumenView(APIView):
    permission_classes = [EsAdminSucursalOSuperAdmin]

    def get(self, request):
        user = request.user
        hoy = timezone.localdate()
        inicio_semana, _ = obtener_rango_periodo("semana")
        inicio_mes, _ = obtener_rango_periodo("mes")

        jornadas = JornadaDiaria.objects.all()
        vehiculos = Vehiculo.objects.all()
        gastos = Gasto.objects.all()
        mantenimientos = Mantenimiento.objects.all()

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")

            if sucursal_id:
                jornadas = jornadas.filter(sucursal_id=sucursal_id)
                vehiculos = vehiculos.filter(sucursal_id=sucursal_id)
                gastos = gastos.filter(sucursal_id=sucursal_id)
                mantenimientos = mantenimientos.filter(sucursal_id=sucursal_id)
            else:
                jornadas = jornadas.filter(sucursal__isnull=True)
                vehiculos = vehiculos.filter(sucursal__isnull=True)
                gastos = gastos.filter(sucursal__isnull=True)
                mantenimientos = mantenimientos.filter(sucursal__isnull=True)

        elif es_admin_sucursal(user):
            if not user.sucursal:
                return Response(
                    {"detail": "Tu usuario no tiene una sucursal asignada."},
                    status=403
                )

            jornadas = jornadas.filter(sucursal=user.sucursal)
            vehiculos = vehiculos.filter(sucursal=user.sucursal)
            gastos = gastos.filter(sucursal=user.sucursal)
            mantenimientos = mantenimientos.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            jornadas = jornadas.filter(
                sucursal=user.sucursal,
                conductor__usuario=user
            )
            vehiculos = vehiculos.filter(
                sucursal=user.sucursal,
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()

            gastos = Gasto.objects.none()
            mantenimientos = Mantenimiento.objects.none()

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        jornadas_hoy = jornadas.filter(fecha=hoy)
        jornadas_semana = jornadas.filter(fecha__gte=inicio_semana, fecha__lte=hoy)
        jornadas_mes = jornadas.filter(fecha__gte=inicio_mes, fecha__lte=hoy)

        gastos_hoy = gastos.filter(fecha=hoy)
        gastos_semana = gastos.filter(fecha__gte=inicio_semana, fecha__lte=hoy)
        gastos_mes = gastos.filter(fecha__gte=inicio_mes, fecha__lte=hoy)

        mantenimientos_hoy = mantenimientos.filter(fecha=hoy)
        mantenimientos_semana = mantenimientos.filter(
            fecha__gte=inicio_semana,
            fecha__lte=hoy
        )
        mantenimientos_mes = mantenimientos.filter(
            fecha__gte=inicio_mes,
            fecha__lte=hoy
        )

        ingreso_dia = sumar_decimal(jornadas_hoy, "ingreso_bruto")
        ingreso_semana = sumar_decimal(jornadas_semana, "ingreso_bruto")
        ingreso_mes = sumar_decimal(jornadas_mes, "ingreso_bruto")

        ganancia_dueno_dia = sumar_decimal(jornadas_hoy, "ganancia_dueno")
        ganancia_dueno_semana = sumar_decimal(jornadas_semana, "ganancia_dueno")
        ganancia_dueno_mes = sumar_decimal(jornadas_mes, "ganancia_dueno")

        gastos_vehiculos_dia = sumar_decimal(gastos_hoy, "monto")
        gastos_vehiculos_semana = sumar_decimal(gastos_semana, "monto")
        gastos_vehiculos_mes = sumar_decimal(gastos_mes, "monto")

        mantenimiento_dia = sumar_decimal(mantenimientos_hoy, "costo")
        mantenimiento_semana = sumar_decimal(mantenimientos_semana, "costo")
        mantenimiento_mes = sumar_decimal(mantenimientos_mes, "costo")

        ganancia_real_dueno_dia = (
            ganancia_dueno_dia
            - gastos_vehiculos_dia
            - mantenimiento_dia
        )

        ganancia_real_dueno_semana = (
            ganancia_dueno_semana
            - gastos_vehiculos_semana
            - mantenimiento_semana
        )

        ganancia_real_dueno_mes = (
            ganancia_dueno_mes
            - gastos_vehiculos_mes
            - mantenimiento_mes
        )

        alertas = []
        for vehiculo in vehiculos:
            alertas.extend(obtener_alertas_vehiculo(vehiculo))

        data = {
            "fecha": str(hoy),

            "ingreso_dia": ingreso_dia,
            "ingreso_semana": ingreso_semana,
            "ingreso_mes": ingreso_mes,

            "ganancia_dueno_dia": ganancia_dueno_dia,
            "ganancia_dueno_semana": ganancia_dueno_semana,
            "ganancia_dueno_mes": ganancia_dueno_mes,

            "gastos_vehiculos_dia": gastos_vehiculos_dia,
            "gastos_vehiculos_semana": gastos_vehiculos_semana,
            "gastos_vehiculos_mes": gastos_vehiculos_mes,

            "mantenimiento_dia": mantenimiento_dia,
            "mantenimiento_semana": mantenimiento_semana,
            "mantenimiento_mes": mantenimiento_mes,

            "ganancia_real_dueno_dia": ganancia_real_dueno_dia,
            "ganancia_real_dueno_semana": ganancia_real_dueno_semana,
            "ganancia_real_dueno_mes": ganancia_real_dueno_mes,

            "pago_taxistas_dia": sumar_decimal(jornadas_hoy, "pago_conductor"),
            "pago_taxistas_semana": sumar_decimal(jornadas_semana, "pago_conductor"),
            "pago_taxistas_mes": sumar_decimal(jornadas_mes, "pago_conductor"),

            "gastos_dia": gastos_vehiculos_dia + mantenimiento_dia,
            "gastos_semana": gastos_vehiculos_semana + mantenimiento_semana,
            "gastos_mes": gastos_vehiculos_mes + mantenimiento_mes,

            "km_dia": sumar_entero(jornadas_hoy, "kilometros_recorridos"),
            "km_semana": sumar_entero(jornadas_semana, "kilometros_recorridos"),
            "km_mes": sumar_entero(jornadas_mes, "kilometros_recorridos"),

            "vehiculos": vehiculos.count(),
            "alertas_mantenimiento": len(alertas),
            "alertas": alertas,
        }

        return Response(data)

class ReporteFinancieroView(APIView):
    permission_classes = [
        EsAdminSucursalOSuperAdmin
    ]

    def _obtener_fechas(self, request):
        periodo = str(
            request.query_params.get(
                "periodo",
                "mes",
            )
        ).strip().lower()

        fecha_inicio_param = request.query_params.get(
            "fecha_inicio"
        )
        fecha_fin_param = request.query_params.get(
            "fecha_fin"
        )

        if fecha_inicio_param or fecha_fin_param:
            fecha_inicio = parse_date(
                fecha_inicio_param or ""
            )
            fecha_fin = parse_date(
                fecha_fin_param or ""
            )

            if not fecha_inicio or not fecha_fin:
                return (
                    periodo,
                    None,
                    None,
                    "Debes seleccionar una fecha inicial y una fecha final válidas.",
                )

            if fecha_inicio > fecha_fin:
                return (
                    periodo,
                    None,
                    None,
                    "La fecha inicial no puede ser mayor que la fecha final.",
                )

            return (
                "personalizado",
                fecha_inicio,
                fecha_fin,
                None,
            )

        fecha_inicio, fecha_fin = (
            obtener_rango_periodo(periodo)
        )

        return (
            periodo,
            fecha_inicio,
            fecha_fin,
            None,
        )

    def _nombre_vehiculo(self, vehiculo):
        if not vehiculo:
            return "Sin vehículo"

        datos = [
            getattr(vehiculo, "numero", ""),
            getattr(vehiculo, "placa", ""),
            getattr(vehiculo, "marca", ""),
            getattr(vehiculo, "modelo", ""),
        ]

        nombre = " - ".join(
            str(dato)
            for dato in datos
            if dato
        ).strip()

        return nombre or f"Vehículo #{vehiculo.pk}"
    def _nombre_conductor(self, conductor):
        if not conductor:
            return "Sin conductor"

        nombre = " ".join(
            parte
            for parte in [
                conductor.nombre,
                conductor.apellido,
            ]
            if parte
        ).strip()

        return nombre or f"Conductor #{conductor.pk}"

    def get(self, request):
        user = request.user

        (
            periodo,
            fecha_inicio,
            fecha_fin,
            error_fechas,
        ) = self._obtener_fechas(request)

        if error_fechas:
            return Response(
                {
                    "detail": error_fechas
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        jornadas = JornadaDiaria.objects.select_related(
            "vehiculo",
            "conductor",
        ).all()

        gastos = Gasto.objects.select_related(
            "vehiculo"
        ).all()

        mantenimientos = Mantenimiento.objects.select_related(
            "vehiculo"
        ).all()

        if es_superadmin(user):
            sucursal_id = str(
                request.query_params.get(
                    "sucursal",
                    "",
                )
            ).strip()

            if sucursal_id:
                jornadas = jornadas.filter(
                    sucursal_id=sucursal_id
                )

                gastos = gastos.filter(
                    sucursal_id=sucursal_id
                )

                mantenimientos = mantenimientos.filter(
                    sucursal_id=sucursal_id
                )

        elif es_admin_sucursal(user):
            if not user.sucursal_id:
                return Response(
                    {
                        "detail": (
                            "Tu usuario no tiene una "
                            "sucursal asignada."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            jornadas = jornadas.filter(
                sucursal_id=user.sucursal_id
            )

            gastos = gastos.filter(
                sucursal_id=user.sucursal_id
            )

            mantenimientos = mantenimientos.filter(
                sucursal_id=user.sucursal_id
            )

        else:
            return Response(
                {
                    "detail": (
                        "No tienes permisos para "
                        "consultar reportes."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        vehiculo_id = str(
            request.query_params.get(
                "vehiculo",
                "",
            )
        ).strip()

        if vehiculo_id:
            if not vehiculo_id.isdigit():
                return Response(
                    {
                        "detail": (
                            "El vehículo seleccionado "
                            "no es válido."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            jornadas = jornadas.filter(
                vehiculo_id=vehiculo_id
            )

            gastos = gastos.filter(
                vehiculo_id=vehiculo_id
            )

            mantenimientos = mantenimientos.filter(
                vehiculo_id=vehiculo_id
            )

        jornadas = jornadas.filter(
            fecha__range=(
                fecha_inicio,
                fecha_fin,
            )
        )

        gastos = gastos.filter(
            fecha__range=(
                fecha_inicio,
                fecha_fin,
            )
        )

        mantenimientos = mantenimientos.filter(
            fecha__range=(
                fecha_inicio,
                fecha_fin,
            )
        )

        total_ingresos = sumar_decimal(
            jornadas,
            "ingreso_bruto",
        )

        total_pago_conductores = sumar_decimal(
            jornadas,
            "pago_conductor",
        )

        total_adelantos = sumar_decimal(
            jornadas,
            "total_adelantos",
        )

        total_ganancia_dueno = sumar_decimal(
            jornadas,
            "ganancia_dueno",
        )

        total_gastos_vehiculos = sumar_decimal(
            gastos,
            "monto",
        )

        total_mantenimiento = sumar_decimal(
            mantenimientos,
            "costo",
        )

        total_gastos_operativos = (
            total_gastos_vehiculos +
            total_mantenimiento
        )

        total_ganancia_real_dueno = (
            total_ganancia_dueno -
            total_gastos_operativos
        )

        resumen_vehiculos = {}

        def obtener_resumen(vehiculo):
            vehiculo_id_local = (
                vehiculo.pk
                if vehiculo
                else 0
            )

            if vehiculo_id_local not in resumen_vehiculos:
                resumen_vehiculos[
                    vehiculo_id_local
                ] = {
                    "vehiculo_id": vehiculo_id_local,
                    "vehiculo": self._nombre_vehiculo(
                        vehiculo
                    ),
                    "jornadas": 0,
                    "kilometros": 0,
                    "ingresos": Decimal("0.00"),
                    "pago_conductores": Decimal(
                        "0.00"
                    ),
                    "ganancia_dueno": Decimal(
                        "0.00"
                    ),
                    "gastos": Decimal("0.00"),
                    "mantenimiento": Decimal(
                        "0.00"
                    ),
                }

            return resumen_vehiculos[
                vehiculo_id_local
            ]

        for jornada in jornadas:
            resumen = obtener_resumen(
                jornada.vehiculo
            )

            resumen["jornadas"] += 1

            resumen["kilometros"] += int(
                jornada.kilometros_recorridos or 0
            )

            resumen["ingresos"] += Decimal(
                str(jornada.ingreso_bruto or 0)
            )

            resumen["pago_conductores"] += Decimal(
                str(jornada.pago_conductor or 0)
            )

            resumen["ganancia_dueno"] += Decimal(
                str(jornada.ganancia_dueno or 0)
            )

        for gasto in gastos:
            resumen = obtener_resumen(
                gasto.vehiculo
            )

            resumen["gastos"] += Decimal(
                str(gasto.monto or 0)
            )

        for mantenimiento in mantenimientos:
            resumen = obtener_resumen(
                mantenimiento.vehiculo
            )

            resumen["mantenimiento"] += Decimal(
                str(mantenimiento.costo or 0)
            )

        detalle_por_vehiculo = []

        for resumen in resumen_vehiculos.values():
            gastos_operativos = (
                resumen["gastos"] +
                resumen["mantenimiento"]
            )

            ganancia_real = (
                resumen["ganancia_dueno"] -
                gastos_operativos
            )

            detalle_por_vehiculo.append(
                {
                    **resumen,
                    "gastos_operativos": (
                        gastos_operativos
                    ),
                    "ganancia_real": ganancia_real,
                }
            )

        detalle_por_vehiculo.sort(
            key=lambda item: (
                item["vehiculo"] or ""
            ).lower()
        )
        
        detalle_jornadas = []

        for jornada in jornadas.order_by(
            "-fecha",
            "-id",
        ):
            detalle_jornadas.append(
                {
                    "jornada_id": jornada.pk,
                    "fecha": str(jornada.fecha),
                    "vehiculo_id": jornada.vehiculo_id,
                    "vehiculo": self._nombre_vehiculo(
                        jornada.vehiculo
                    ),
                    "conductor_id": jornada.conductor_id,
                    "conductor": self._nombre_conductor(
                        jornada.conductor
                    ),
                    "tipo_cobro": jornada.tipo_cobro,
                    "tipo_cobro_nombre": (
                        jornada.get_tipo_cobro_display()
                    ),
                    "kilometraje_inicial": (
                        jornada.kilometraje_inicial
                    ),
                    "kilometraje_final": (
                        jornada.kilometraje_final
                    ),
                    "kilometros": (
                        jornada.kilometros_recorridos
                    ),
                    "ingreso_bruto": (
                        jornada.ingreso_bruto
                    ),
                    "monto_alquiler": (
                        jornada.monto_alquiler
                    ),
                    "pago_conductor": (
                        jornada.pago_conductor
                    ),
                    "adelantos": (
                        jornada.total_adelantos
                    ),
                    "ganancia_dueno": (
                        jornada.ganancia_dueno
                    ),
                }
            )

        return Response(
            {
                "periodo": periodo,
                "fecha_inicio": str(fecha_inicio),
                "fecha_fin": str(fecha_fin),
                "vehiculo_seleccionado": (
                    vehiculo_id or None
                ),

                "total_ingresos": total_ingresos,
                "total_pago_conductores": (
                    total_pago_conductores
                ),
                "total_adelantos": total_adelantos,
                "total_ganancia_dueno": (
                    total_ganancia_dueno
                ),

                "total_gastos_vehiculos": (
                    total_gastos_vehiculos
                ),
                "total_mantenimiento": (
                    total_mantenimiento
                ),
                "total_gastos_operativos": (
                    total_gastos_operativos
                ),
                "total_ganancia_real_dueno": (
                    total_ganancia_real_dueno
                ),

                "total_gastos": (
                    total_gastos_operativos
                ),
                "total_jornadas": jornadas.count(),
                "total_registros_gastos": (
                    gastos.count()
                ),
                "total_registros_mantenimiento": (
                    mantenimientos.count()
                ),

                "detalle_por_vehiculo": (
                    detalle_por_vehiculo
                ),
                "detalle_jornadas": detalle_jornadas,
            }
        )



class ReporteFinancieroExcelView(
    ReporteFinancieroView
):
    permission_classes = [
        EsAdminSucursalOSuperAdmin
    ]

    def get(self, request):
        respuesta_reporte = super().get(
            request
        )

        if respuesta_reporte.status_code != 200:
            return respuesta_reporte

        reporte = respuesta_reporte.data

        libro = Workbook()
        hoja = libro.active
        hoja.title = "Reporte financiero"

        color_amarillo = "F5B800"
        color_amarillo_claro = "FFF4CF"
        color_azul = "1D4ED8"
        color_verde = "059669"
        color_rojo = "DC2626"
        color_naranja = "EA580C"
        color_gris = "F1F5F9"
        color_texto = "0F172A"
        color_borde = "CBD5E1"

        borde_fino = Border(
            left=Side(
                style="thin",
                color=color_borde,
            ),
            right=Side(
                style="thin",
                color=color_borde,
            ),
            top=Side(
                style="thin",
                color=color_borde,
            ),
            bottom=Side(
                style="thin",
                color=color_borde,
            ),
        )

        hoja.merge_cells("A1:I1")

        celda_titulo = hoja["A1"]
        celda_titulo.value = (
            "TAXICONTROL - REPORTE FINANCIERO"
        )
        celda_titulo.font = Font(
            bold=True,
            size=16,
            color="FFFFFF",
        )
        celda_titulo.fill = PatternFill(
            "solid",
            fgColor=color_amarillo,
        )
        celda_titulo.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        hoja.row_dimensions[1].height = 30

        hoja.merge_cells("A2:I2")

        celda_periodo = hoja["A2"]
        celda_periodo.value = (
            f"Período: "
            f"{reporte['fecha_inicio']} "
            f"al {reporte['fecha_fin']}"
        )
        celda_periodo.font = Font(
            bold=True,
            size=11,
            color=color_texto,
        )
        celda_periodo.fill = PatternFill(
            "solid",
            fgColor=color_amarillo_claro,
        )
        celda_periodo.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        hoja.merge_cells("A4:B4")

        celda_resumen = hoja["A4"]
        celda_resumen.value = "RESUMEN GENERAL"
        celda_resumen.font = Font(
            bold=True,
            size=12,
            color="FFFFFF",
        )
        celda_resumen.fill = PatternFill(
            "solid",
            fgColor=color_azul,
        )
        celda_resumen.alignment = Alignment(
            horizontal="left",
            vertical="center",
        )

        resumen = [
            (
                "Ingresos",
                reporte.get(
                    "total_ingresos",
                    0,
                ),
                color_verde,
            ),
            (
                "Pago a conductores",
                reporte.get(
                    "total_pago_conductores",
                    0,
                ),
                color_azul,
            ),
            (
                "Ganancia del dueño",
                reporte.get(
                    "total_ganancia_dueno",
                    0,
                ),
                color_amarillo,
            ),
            (
                "Gastos de vehículos",
                reporte.get(
                    "total_gastos_vehiculos",
                    0,
                ),
                color_rojo,
            ),
            (
                "Mantenimiento",
                reporte.get(
                    "total_mantenimiento",
                    0,
                ),
                color_naranja,
            ),
            (
                "Gastos operativos",
                reporte.get(
                    "total_gastos_operativos",
                    0,
                ),
                color_rojo,
            ),
            (
                "Ganancia real",
                reporte.get(
                    "total_ganancia_real_dueno",
                    0,
                ),
                color_verde,
            ),
        ]

        fila_resumen = 5

        for etiqueta, valor, color in resumen:
            celda_etiqueta = hoja.cell(
                fila_resumen,
                1,
                etiqueta,
            )

            celda_valor = hoja.cell(
                fila_resumen,
                2,
                float(valor or 0),
            )

            celda_etiqueta.font = Font(
                bold=True,
                color=color_texto,
            )

            celda_etiqueta.fill = PatternFill(
                "solid",
                fgColor=color_gris,
            )

            celda_valor.font = Font(
                bold=True,
                color=color,
            )

            celda_valor.number_format = (
                '"C$" #,##0.00'
            )

            for columna in [1, 2]:
                hoja.cell(
                    fila_resumen,
                    columna,
                ).border = borde_fino

            fila_resumen += 1

        fila_tabla = 14

        hoja.merge_cells(
            start_row=fila_tabla,
            start_column=1,
            end_row=fila_tabla,
            end_column=9,
        )

        titulo_tabla = hoja.cell(
            fila_tabla,
            1,
            "DETALLE DE JORNADAS ORDENADO POR FECHA",
        )

        titulo_tabla.font = Font(
            bold=True,
            size=12,
            color="FFFFFF",
        )

        titulo_tabla.fill = PatternFill(
            "solid",
            fgColor=color_azul,
        )

        titulo_tabla.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

        encabezados = [
            "Fecha",
            "Vehículo",
            "Conductor",
            "Tipo de cobro",
            "Kilómetros",
            "Ingreso",
            "Pago conductor",
            "Ganancia dueño",
        ]

        fila_encabezados = fila_tabla + 1

        for columna, encabezado in enumerate(
            encabezados,
            start=1,
        ):
            celda = hoja.cell(
                fila_encabezados,
                columna,
                encabezado,
            )

            celda.font = Font(
                bold=True,
                color="FFFFFF",
            )

            celda.fill = PatternFill(
                "solid",
                fgColor=color_amarillo,
            )

            celda.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

            celda.border = borde_fino

        fila_datos = fila_encabezados + 1

        detalle_jornadas = reporte.get(
            "detalle_jornadas",
            [],
        )

        total_kilometros = sum(
            int(
                item.get(
                    "kilometros",
                    0,
                ) or 0
            )
            for item in detalle_jornadas
        )

        for item in detalle_jornadas:
            datos = [
                item.get("fecha", "-"),
                item.get("vehiculo", "-"),
                item.get("conductor", "-"),
                item.get(
                    "tipo_cobro_nombre",
                    "-",
                ),
                int(
                    item.get(
                        "kilometros",
                        0,
                    ) or 0
                ),
                float(
                    item.get(
                        "ingreso_bruto",
                        0,
                    ) or 0
                ),
                float(
                    item.get(
                        "pago_conductor",
                        0,
                    ) or 0
                ),
              
                float(
                    item.get(
                        "ganancia_dueno",
                        0,
                    ) or 0
                ),
            ]

            for columna, valor in enumerate(
                datos,
                start=1,
            ):
                celda = hoja.cell(
                    fila_datos,
                    columna,
                    valor,
                )

                celda.border = borde_fino

                celda.alignment = Alignment(
                    horizontal=(
                        "left"
                        if columna <= 4
                        else "right"
                    ),
                    vertical="center",
                )

                if columna >= 6:
                    celda.number_format = (
                        '"C$" #,##0.00'
                    )

            hoja.cell(
                fila_datos,
                6,
            ).font = Font(
                bold=True,
                color=color_verde,
            )

            hoja.cell(
                fila_datos,
                7,
            ).font = Font(
                bold=True,
                color=color_azul,
            )

            hoja.cell(
                fila_datos,
                8,
            ).font = Font(
                bold=True,
                color=color_rojo,
            )

            hoja.cell(
                fila_datos,
                9,
            ).font = Font(
                bold=True,
                color=color_amarillo,
            )

            fila_datos += 1

        if detalle_jornadas:
            hoja.merge_cells(
                start_row=fila_datos,
                start_column=1,
                end_row=fila_datos,
                end_column=4,
            )

            celda_total = hoja.cell(
                fila_datos,
                1,
                "TOTALES DEL PERÍODO",
            )

            celda_total.font = Font(
                bold=True,
                color="FFFFFF",
            )

            celda_total.fill = PatternFill(
                "solid",
                fgColor=color_azul,
            )

            celda_total.alignment = Alignment(
                horizontal="right",
                vertical="center",
            )

            hoja.cell(
                fila_datos,
                5,
                total_kilometros,
            )

            hoja.cell(
                fila_datos,
                6,
                float(
                    reporte.get(
                        "total_ingresos",
                        0,
                    ) or 0
                ),
            )

            hoja.cell(
                fila_datos,
                7,
                float(
                    reporte.get(
                        "total_pago_conductores",
                        0,
                    ) or 0
                ),
            )

            hoja.cell(
                fila_datos,
                8,
                float(
                    reporte.get(
                        "total_adelantos",
                        0,
                    ) or 0
                ),
            )

            hoja.cell(
                fila_datos,
                9,
                float(
                    reporte.get(
                        "total_ganancia_dueno",
                        0,
                    ) or 0
                ),
            )

            for columna in range(1, 10):
                celda = hoja.cell(
                    fila_datos,
                    columna,
                )

                celda.border = borde_fino

                if columna >= 5:
                    celda.fill = PatternFill(
                        "solid",
                        fgColor=color_gris,
                    )

                    celda.font = Font(
                        bold=True,
                        color=(
                            color_verde
                            if columna == 6
                            else color_azul
                            if columna == 7
                            else color_rojo
                            if columna == 8
                            else color_amarillo
                            if columna == 9
                            else color_texto
                        ),
                    )

                    celda.alignment = Alignment(
                        horizontal="right",
                        vertical="center",
                    )

                if columna >= 6:
                    celda.number_format = (
                        '"C$" #,##0.00'
                    )

        else:
            hoja.merge_cells(
                start_row=fila_datos,
                start_column=1,
                end_row=fila_datos,
                end_column=9,
            )

            celda_vacia = hoja.cell(
                fila_datos,
                1,
                "No hay jornadas para los filtros seleccionados.",
            )

            celda_vacia.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

            celda_vacia.font = Font(
                italic=True,
                color="64748B",
            )

        anchos = {
            "A": 14,
            "B": 30,
            "C": 26,
            "D": 17,
            "E": 14,
            "F": 17,
            "G": 19,
            "H": 16,
            "I": 19,
        }

        for columna, ancho in anchos.items():
            hoja.column_dimensions[
                columna
            ].width = ancho

        hoja.freeze_panes = "A16"

        hoja.sheet_view.showGridLines = False

        hoja.page_setup.orientation = "landscape"
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0

        hoja.sheet_properties.pageSetUpPr.fitToPage = True

        respuesta = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        respuesta[
            "Content-Disposition"
        ] = (
            "attachment; "
            "filename=reporte_financiero_taxi_control.xlsx"
        )

        libro.save(respuesta)

        return respuesta


class ReporteKilometrajeView(APIView):
    permission_classes = [EsAdminSucursalOSuperAdmin]

    def get(self, request):
        user = request.user
        periodo = request.query_params.get("periodo", "dia")
        fecha_inicio, fecha_fin = obtener_rango_periodo(periodo)

        jornadas = JornadaDiaria.objects.select_related(
            "conductor",
            "vehiculo",
            "sucursal"
        ).filter(
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")
            if sucursal_id:
                jornadas = jornadas.filter(sucursal_id=sucursal_id)

        elif es_admin_sucursal(user):
            jornadas = jornadas.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            jornadas = jornadas.filter(sucursal=user.sucursal, conductor__usuario=user)

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        detalle = []
        for jornada in jornadas.order_by("-fecha", "-id"):
            detalle.append({
                "id": jornada.id,
                "fecha": str(jornada.fecha),
                "sucursal": jornada.sucursal.nombre,
                "conductor": f"{jornada.conductor.nombre} {jornada.conductor.apellido}".strip(),
                "vehiculo": jornada.vehiculo.placa,
                "numero_vehiculo": jornada.vehiculo.numero,
                "km_inicial": jornada.kilometraje_inicial,
                "km_final": jornada.kilometraje_final,
                "km_recorridos": jornada.kilometros_recorridos,
            })

        return Response({
            "periodo": periodo,
            "fecha_inicio": str(fecha_inicio),
            "fecha_fin": str(fecha_fin),
            "total_kilometros": sumar_entero(jornadas, "kilometros_recorridos"),
            "detalle": detalle,
        })


class AlertasMantenimientoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        hoy = timezone.localdate()
        ahora = timezone.now().isoformat()

        vehiculos = Vehiculo.objects.select_related("sucursal", "estado").all()
        conductores = Conductor.objects.select_related("sucursal").filter(activo=True)

        if es_superadmin(user):
            vehiculos = vehiculos.filter(
                sucursal__isnull=True
            )

            conductores = conductores.filter(
                sucursal__isnull=True
            )

        elif es_admin_sucursal(user):
            vehiculos = vehiculos.filter(sucursal=user.sucursal)
            conductores = conductores.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            vehiculos = vehiculos.filter(
                sucursal=user.sucursal,
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()
            conductores = conductores.filter(usuario=user)

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        # Tipo de mantenimiento "aceite" (se crea si no existe en el catálogo).
        tipo_aceite, _ = TipoMantenimiento.objects.get_or_create(
            codigo="aceite",
            defaults={"nombre": "Cambio de aceite", "intervalo_km": 5000},
        )

        config_cache = {}

        def config_de(sucursal):
            clave = sucursal.id if sucursal else None
            if clave not in config_cache:
                config_cache[clave] = obtener_configuracion_sucursal(sucursal)
            return config_cache[clave]

        alertas = []

        for vehiculo in vehiculos:
            alerta = construir_alerta_km_aceite(
                vehiculo, config_de(vehiculo.sucursal), tipo_aceite, ahora
            )
            if alerta:
                alertas.append(alerta)

        for conductor in conductores:
            alerta = construir_alerta_licencia(conductor, hoy, ahora)
            if alerta:
                alertas.append(alerta)

        # Más urgentes primero.
        orden = {"critical": 0, "warning": 1, "info": 2}
        alertas.sort(key=lambda a: orden.get(a["severidad"], 3))

        return Response(alertas)

class DashboardFinancieroView(APIView):
    permission_classes = [EsAdminSucursalOSuperAdmin]

    def get_queryset_por_usuario(self, modelo):
        user = self.request.user

        if not user or not user.is_authenticated:
            return modelo.objects.none()

        codigo_rol = user.rol.codigo if getattr(user, "rol", None) else ""

        if codigo_rol in ["superadmin", "super_admin"]:
            return modelo.objects.filter(sucursal__isnull=True)

        if codigo_rol == "admin_sucursal":
            if not user.sucursal:
                return modelo.objects.none()
            return modelo.objects.filter(sucursal=user.sucursal)

        if codigo_rol == "taxista":
            if modelo.__name__ == "JornadaDiaria":
                return modelo.objects.filter(conductor__usuario=user)
            return modelo.objects.none()

        return modelo.objects.none()

    def get(self, request):
        anio = request.query_params.get("anio")

        try:
            anio = int(anio) if anio else timezone.now().year
        except ValueError:
            anio = timezone.now().year

        jornadas_qs = self.get_queryset_por_usuario(JornadaDiaria).filter(
            fecha__year=anio
        )

        gastos_qs = self.get_queryset_por_usuario(Gasto).filter(
            fecha__year=anio
        )

        mantenimientos_qs = self.get_queryset_por_usuario(Mantenimiento).filter(
            fecha__year=anio
        )

        ingresos_por_mes = (
            jornadas_qs.annotate(mes=TruncMonth("fecha"))
            .values("mes")
            .annotate(
                ingresos=Sum("ingreso_bruto"),
                ganancia_base=Sum("ganancia_dueno"),
                pago_taxistas=Sum("pago_conductor"),
                kilometros=Sum("kilometros_recorridos"),
            )
            .order_by("mes")
        )

        gastos_por_mes = (
            gastos_qs.annotate(mes=TruncMonth("fecha"))
            .values("mes")
            .annotate(total=Sum("monto"))
            .order_by("mes")
        )

        mantenimiento_por_mes = (
            mantenimientos_qs.annotate(mes=TruncMonth("fecha"))
            .values("mes")
            .annotate(total=Sum("costo"))
            .order_by("mes")
        )

        gastos_map = {
            item["mes"].strftime("%Y-%m"): item["total"] or Decimal("0.00")
            for item in gastos_por_mes
            if item["mes"]
        }

        mantenimiento_map = {
            item["mes"].strftime("%Y-%m"): item["total"] or Decimal("0.00")
            for item in mantenimiento_por_mes
            if item["mes"]
        }

        ingresos_map = {}

        for item in ingresos_por_mes:
            if not item["mes"]:
                continue

            key = item["mes"].strftime("%Y-%m")

            ingresos = item["ingresos"] or Decimal("0.00")
            ganancia_base = item["ganancia_base"] or Decimal("0.00")
            pago_taxistas = item["pago_taxistas"] or Decimal("0.00")
            kilometros = item["kilometros"] or 0

            ingresos_map[key] = {
                "ingresos": ingresos,
                "ganancia_base": ganancia_base,
                "pago_taxistas": pago_taxistas,
                "kilometros": kilometros,
            }

        data = []

        for mes in range(1, 13):
            key = f"{anio}-{str(mes).zfill(2)}"

            ingresos_data = ingresos_map.get(
                key,
                {
                    "ingresos": Decimal("0.00"),
                    "ganancia_base": Decimal("0.00"),
                    "pago_taxistas": Decimal("0.00"),
                    "kilometros": 0,
                },
            )

            gastos = gastos_map.get(key, Decimal("0.00"))
            mantenimiento = mantenimiento_map.get(key, Decimal("0.00"))
            gastos_operativos = gastos + mantenimiento

            ganancia_real = (
                    ingresos_data["ganancia_base"]
                    - gastos_operativos
                ).quantize(
                    Decimal("0.01")
)
            data.append(
                {
                    "mes": key,
                    "ingresos": float(ingresos_data["ingresos"]),
                    "ganancia_base": float(ingresos_data["ganancia_base"]),
                    "pago_taxistas": float(ingresos_data["pago_taxistas"]),
                    "gastos_vehiculos": float(gastos),
                    "mantenimiento": float(mantenimiento),
                    "gastos_operativos": float(gastos_operativos),
                    "ganancia_real": float(ganancia_real),
                    "kilometros": int(ingresos_data["kilometros"] or 0),
                }
            )

        return Response(data)

def _decimal(valor):
    try:
        numero = Decimal(str(valor or "0.00"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"detail": "El monto enviado no es válido."})

    if not numero.is_finite():
        raise ValidationError({"detail": "El monto enviado no es válido."})

    return numero.quantize(Decimal("0.01"))


def _tipo_movimiento_adelanto(adelanto):
    codigo = (
        adelanto.estado.codigo
        if adelanto.estado
        else ""
    )

    codigo = str(codigo).strip().lower()

    if codigo in ["abono", "abonado"]:
        return "ABONO"

    return "ADELANTO"


def _serializar_jornada_liquidacion(jornada):
    vehiculo = jornada.vehiculo

    return {
        "id": jornada.id,
        "fecha": jornada.fecha,
        "vehiculo": str(vehiculo) if vehiculo else "",
        "vehiculo_id": jornada.vehiculo_id,
        "kilometraje_inicial": jornada.kilometraje_inicial,
        "kilometraje_final": jornada.kilometraje_final,
        "kilometros_recorridos": jornada.kilometros_recorridos,
        "ingreso_bruto": jornada.ingreso_bruto,
        "pago_conductor": jornada.pago_conductor,
        "total_adelantos": jornada.total_adelantos,
        "pago_pendiente_conductor": jornada.pago_pendiente_conductor,
        "ganancia_dueno": jornada.ganancia_dueno,
    }


def _serializar_liquidacion(liquidacion):
    detalles = liquidacion.detalles.all().order_by("fecha", "id")

    return {
        "id": liquidacion.pk,
        "liquidacion_id": liquidacion.pk,


       "conductor": {
        "id": liquidacion.conductor_id,
        "nombre": f"{liquidacion.conductor.nombre} {liquidacion.conductor.apellido}".strip(),
        "cedula": liquidacion.conductor.cedula,
        "telefono": liquidacion.conductor.telefono or "",
    },
        "conductor_nombre": f"{liquidacion.conductor.nombre} {liquidacion.conductor.apellido}".strip(),
        "conductor_telefono": liquidacion.conductor.telefono or "",
        "cedula": liquidacion.conductor.cedula,
        "fecha": liquidacion.fecha,
        "fecha_inicio": liquidacion.fecha_inicio,
        "fecha_fin": liquidacion.fecha_fin,
        "jornadas_count": liquidacion.jornadas_count,
        "total_jornadas": liquidacion.total_jornadas,
        "total_adelantos_pendientes": liquidacion.total_adelantos_pendientes,
        "abono_aplicado": liquidacion.abono_aplicado,
        "ajuste_manual": liquidacion.ajuste_manual,
        "total_pago": liquidacion.total_pago,
        "notas": liquidacion.notas or "",
        "jornadas": [
            {
                "id": detalle.jornada_id,
                "fecha": detalle.fecha,
                "vehiculo": detalle.vehiculo,
                "kilometros_recorridos": detalle.kilometros_recorridos,
                "ingreso_bruto": detalle.ingreso_bruto,
                "pago_conductor": detalle.pago_conductor,
            }
            for detalle in detalles
        ],
    }


def _obtener_jornadas_pendientes_liquidacion(
    user,
    conductor,
):
    jornadas = (
        JornadaDiaria.objects
        .select_related(
            "conductor",
            "vehiculo",
            "sucursal",
        )
        .filter(
            conductor=conductor,
            kilometraje_final__isnull=False,
            pago_pendiente_conductor__gt=Decimal("0.00"),
            detalles_liquidacion__isnull=True,
        )
        .distinct()
    )

    if es_superadmin(user):
        if conductor.sucursal_id is None:
            jornadas = jornadas.filter(
                sucursal__isnull=True
            )
        else:
            jornadas = jornadas.filter(
                sucursal=conductor.sucursal
            )

    elif es_admin_sucursal(user):
        jornadas = jornadas.filter(
            sucursal=user.sucursal
        )

    elif es_taxista(user):
        jornadas = jornadas.filter(
            conductor__usuario=user
        )

    else:
        jornadas = (
            JornadaDiaria.objects.none()
        )

    return jornadas

def _calcular_preview_liquidacion(user, conductor):
    jornadas = _obtener_jornadas_pendientes_liquidacion(user, conductor)

    total_jornadas = jornadas.aggregate(
        total=Sum("pago_conductor")
    )["total"] or Decimal("0.00")

    adelantos = Adelanto.objects.select_related(
        "estado",
        "conductor"
    ).filter(
        conductor=conductor
    ).order_by("fecha", "id")

    if es_superadmin(user):
        if conductor.sucursal_id is None:
            adelantos = adelantos.filter(sucursal__isnull=True)
        else:
            adelantos = adelantos.filter(sucursal=conductor.sucursal)

    elif es_admin_sucursal(user):
        adelantos = adelantos.filter(sucursal=user.sucursal)

    elif es_taxista(user):
        adelantos = adelantos.filter(conductor__usuario=user)

    total_adelantos = Decimal("0.00")
    total_abonos = Decimal("0.00")
    historial_adelantos = []

    for movimiento in adelantos:
        tipo = _tipo_movimiento_adelanto(movimiento)
        monto = Decimal(movimiento.monto or "0.00")

        if tipo == "ABONO":
            total_abonos += monto
        else:
            total_adelantos += monto

        historial_adelantos.append({
            "id": movimiento.id,
            "fecha": movimiento.fecha,
            "tipo": tipo,
            "tipo_display": "Abono" if tipo == "ABONO" else "Adelanto",
            "estado_nombre": movimiento.estado.nombre if movimiento.estado else "Sin estado",
            "estado_codigo": movimiento.estado.codigo if movimiento.estado else None,
            "monto": movimiento.monto,
            "observacion": movimiento.observacion or "",
        })

    pendiente_adelantos = total_adelantos - total_abonos

    if pendiente_adelantos < 0:
        pendiente_adelantos = Decimal("0.00")

    fechas = list(jornadas.values_list("fecha", flat=True))

    return {
        "conductor": {
            "id": conductor.id,
            "nombre": f"{conductor.nombre} {conductor.apellido}".strip(),
            "cedula": conductor.cedula,
            "sucursal": conductor.sucursal_id,
            "sucursal_nombre": conductor.sucursal.nombre if conductor.sucursal else None,
        },
        "jornadas_count": jornadas.count(),
        "fecha_inicio": min(fechas) if fechas else None,
        "fecha_fin": max(fechas) if fechas else None,
        "total_jornadas": total_jornadas,
        "total_adelantos": total_adelantos,
        "total_abonos": total_abonos,
        "pendiente_adelantos": pendiente_adelantos,
        "historial_adelantos": historial_adelantos,
        "jornadas": [
            _serializar_jornada_liquidacion(jornada)
            for jornada in jornadas
        ],
        "_jornadas_queryset": jornadas,
    }


class LiquidacionPreviewView(APIView):
    permission_classes = [EsAdminSucursalOSuperAdmin]

    def get(self, request):
        conductor_id = request.query_params.get("conductor_id")

        if not conductor_id:
            return Response(
                {"detail": "Debes seleccionar un conductor."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conductor = Conductor.objects.select_related("sucursal").get(id=conductor_id)
        except Conductor.DoesNotExist:
            return Response(
                {"detail": "El conductor seleccionado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        user = request.user

        if es_admin_sucursal(user):
            if not user.sucursal:
                return Response(
                    {"detail": "Tu usuario no tiene una sucursal asignada."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if conductor.sucursal_id != user.sucursal_id:
                return Response(
                    {"detail": "No puedes liquidar conductores de otra sucursal."},
                    status=status.HTTP_403_FORBIDDEN
                )

        preview = _calcular_preview_liquidacion(user, conductor)
        preview.pop("_jornadas_queryset", None)

        return Response(preview, status=status.HTTP_200_OK)


class LiquidacionView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get(self, request):
        user = request.user

        liquidaciones = Liquidacion.objects.select_related(
            "conductor",
            "sucursal",
            "usuario"
        ).prefetch_related(
            "detalles"
        ).all()

        if es_superadmin(user):
            liquidaciones = liquidaciones.filter(sucursal__isnull=True)

        elif es_admin_sucursal(user):
            if not user.sucursal:
                return Response(
                    {"detail": "Tu usuario no tiene una sucursal asignada."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            liquidaciones = liquidaciones.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            liquidaciones = liquidaciones.filter(conductor__usuario=user)

        else:
            return Response(
                {"detail": "No tienes permiso para consultar liquidaciones."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = [
            _serializar_liquidacion(liquidacion)
            for liquidacion in liquidaciones
        ]

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user

        if not (es_superadmin(user) or es_admin_sucursal(user)):
            return Response(
                {"detail": "No tienes permiso para registrar liquidaciones."},
                status=status.HTTP_403_FORBIDDEN
            )

        conductor_id = request.data.get("conductor_id") or request.data.get("conductor")

        if not conductor_id:
            return Response(
                {"detail": "Debes seleccionar un conductor."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conductor = Conductor.objects.select_related("sucursal").get(id=conductor_id)
        except Conductor.DoesNotExist:
            return Response(
                {"detail": "El conductor seleccionado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        if es_admin_sucursal(user):
            if not user.sucursal:
                return Response(
                    {"detail": "Tu usuario no tiene una sucursal asignada."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if conductor.sucursal_id != user.sucursal_id:
                return Response(
                    {"detail": "No puedes liquidar conductores de otra sucursal."},
                    status=status.HTTP_403_FORBIDDEN
                )

        abono_aplicado = _decimal(request.data.get("abono_aplicado"))
        ajuste_manual = _decimal(request.data.get("ajuste_manual"))
        notas = request.data.get("notas", "")

        if abono_aplicado < 0:
            return Response(
                {"detail": "El abono aplicado no puede ser negativo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if ajuste_manual < 0:
            return Response(
                {"detail": "El ajuste manual no puede ser negativo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        preview = _calcular_preview_liquidacion(user, conductor)
        jornadas = preview["_jornadas_queryset"]

        if not jornadas.exists():
            return Response(
                {"detail": "Este conductor no tiene jornadas pendientes de liquidación."},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_jornadas = Decimal(preview["total_jornadas"] or "0.00")
        pendiente_adelantos = Decimal(preview["pendiente_adelantos"] or "0.00")

        if abono_aplicado > pendiente_adelantos:
            return Response(
                {"detail": "El abono aplicado no puede ser mayor al saldo pendiente de adelantos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_pago = total_jornadas - abono_aplicado + ajuste_manual

        if total_pago < 0:
            total_pago = Decimal("0.00")

        sucursal = conductor.sucursal

        if es_superadmin(user) and conductor.sucursal_id is None:
            sucursal = None

        if es_admin_sucursal(user):
            sucursal = user.sucursal

        with transaction.atomic():
            liquidacion = Liquidacion.objects.create(
                sucursal=sucursal,
                conductor=conductor,
                usuario=user,
                fecha=timezone.localdate(),
                fecha_inicio=preview["fecha_inicio"],
                fecha_fin=preview["fecha_fin"],
                jornadas_count=preview["jornadas_count"],
                total_jornadas=total_jornadas,
                total_adelantos_pendientes=pendiente_adelantos,
                abono_aplicado=abono_aplicado,
                ajuste_manual=ajuste_manual,
                total_pago=total_pago,
                notas=notas,
            )

            for jornada in jornadas:
                DetalleLiquidacion.objects.create(
                    liquidacion=liquidacion,
                    jornada=jornada,
                    fecha=jornada.fecha,
                    vehiculo=str(jornada.vehiculo) if jornada.vehiculo else "",
                    kilometros_recorridos=jornada.kilometros_recorridos,
                    ingreso_bruto=jornada.ingreso_bruto,
                    pago_conductor=jornada.pago_conductor,
                )

            if abono_aplicado > 0:
                estado_abono, _ = EstadoAdelanto.objects.get_or_create(
                    codigo="abono",
                    defaults={
                        "nombre": "Abono",
                        "activo": True,
                    }
                )

                Adelanto.objects.create(
                    sucursal=sucursal,
                    conductor=conductor,
                    estado=estado_abono,
                    monto=abono_aplicado,
                    fecha=timezone.localdate(),
                    observacion=f"Abono aplicado en liquidación #{liquidacion.id}",
                )

            jornadas.update(
                pago_pendiente_conductor=Decimal("0.00"),
                saldo_adelanto_excedente=Decimal("0.00")
            )

        liquidacion = Liquidacion.objects.select_related(
            "conductor",
            "sucursal",
            "usuario"
        ).prefetch_related(
            "detalles"
        ).get(id=liquidacion.id)

        return Response(
            _serializar_liquidacion(liquidacion),
            status=status.HTTP_201_CREATED
        )


class LiquidacionReciboView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        user = request.user

        try:
            liquidacion = Liquidacion.objects.select_related(
                "conductor",
                "sucursal",
                "usuario"
            ).prefetch_related(
                "detalles"
            ).get(pk=pk)
        except Liquidacion.DoesNotExist:
            return Response(
                {"detail": "La liquidación solicitada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        if es_admin_sucursal(user):
            if liquidacion.sucursal_id != user.sucursal_id:
                return Response(
                    {"detail": "No puedes ver liquidaciones de otra sucursal."},
                    status=status.HTTP_403_FORBIDDEN
                )

        elif es_taxista(user):
            if liquidacion.conductor.usuario_id != user.id:
                return Response(
                    {"detail": "No puedes ver liquidaciones de otro conductor."},
                    status=status.HTTP_403_FORBIDDEN
                )

        elif not es_superadmin(user):
            return Response(
                {"detail": "No tienes permiso para ver esta liquidación."},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            _serializar_liquidacion(liquidacion),
            status=status.HTTP_200_OK
        )

class PaginacionAuditoria(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 50


class AuditoriaView(APIView):
    permission_classes = [IsAuthenticated]

    EVENTOS_MANUALES = {
        "reporte_consultado": {
            "accion": "consulta",
            "modulo": "Reportes",
            "descripcion": "Consultó el reporte financiero.",
        },
        "reporte_excel_descargado": {
            "accion": "descarga",
            "modulo": "Reportes",
            "descripcion": "Descargó el reporte financiero en Excel.",
        },
        "recibo_abierto": {
            "accion": "consulta",
            "modulo": "Liquidaciones",
            "descripcion": "Abrió el recibo de una liquidación.",
        },
        "recibo_pdf_descargado": {
            "accion": "descarga",
            "modulo": "Liquidaciones",
            "descripcion": "Descargó el PDF del recibo de liquidación.",
        },
        "recibo_impreso": {
            "accion": "impresion",
            "modulo": "Liquidaciones",
            "descripcion": "Mandó a imprimir el recibo de liquidación.",
        },
        "recibo_compartido": {
            "accion": "compartir",
            "modulo": "Liquidaciones",
            "descripcion": "Compartió el PDF del recibo de liquidación.",
        },
        "whatsapp_abierto": {
            "accion": "whatsapp",
            "modulo": "Liquidaciones",
            "descripcion": "Abrió WhatsApp para enviar una liquidación.",
        },
        "plantilla_whatsapp_guardada": {
            "accion": "configuracion",
            "modulo": "Liquidaciones",
            "descripcion": (
                "Actualizó la plantilla de mensaje "
                "para liquidaciones por WhatsApp."
            ),
        },
        "plantilla_whatsapp_restaurada": {
            "accion": "configuracion",
            "modulo": "Liquidaciones",
            "descripcion": (
                "Restauró la plantilla predeterminada "
                "de WhatsApp para liquidaciones."
            ),
        },
    }

    def get(self, request):
        usuario = request.user

        if es_superadmin(usuario):
            movimientos = MovimientoAuditoria.objects.select_related(
                "usuario",
                "sucursal",
            ).all()

        elif es_admin_sucursal(usuario):
            if not usuario.sucursal_id:
                movimientos = MovimientoAuditoria.objects.none()
            else:
                movimientos = MovimientoAuditoria.objects.select_related(
                    "usuario",
                    "sucursal",
                ).filter(
                    sucursal_id=usuario.sucursal_id,
                )

        else:
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar "
                        "los movimientos del sistema."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        fecha_inicio = request.query_params.get("fecha_inicio")
        fecha_fin = request.query_params.get("fecha_fin")
        usuario_id = request.query_params.get("usuario")
        accion = request.query_params.get("accion")
        modulo = request.query_params.get("modulo")
        buscar = request.query_params.get("buscar", "").strip()

        if fecha_inicio:
            movimientos = movimientos.filter(
                fecha__date__gte=fecha_inicio,
            )

        if fecha_fin:
            movimientos = movimientos.filter(
                fecha__date__lte=fecha_fin,
            )

        if usuario_id:
            movimientos = movimientos.filter(
                usuario_id=usuario_id,
            )

        if accion:
            movimientos = movimientos.filter(
                accion=accion,
            )

        if modulo:
            movimientos = movimientos.filter(
                modulo__icontains=modulo,
            )

        if buscar:
            movimientos = movimientos.filter(
                Q(descripcion__icontains=buscar)
                | Q(modulo__icontains=buscar)
                | Q(usuario__username__icontains=buscar)
                | Q(usuario__first_name__icontains=buscar)
                | Q(usuario__last_name__icontains=buscar)
            )

        paginador = PaginacionAuditoria()

        pagina = paginador.paginate_queryset(
            movimientos,
            request,
        )

        serializer = MovimientoAuditoriaSerializer(
            pagina,
            many=True,
        )

        return paginador.get_paginated_response(
            serializer.data
        )

    def post(self, request):
        evento = str(
            request.data.get("evento", "")
        ).strip()

        referencia = str(
            request.data.get("referencia", "")
        ).strip()[:250]

        configuracion = self.EVENTOS_MANUALES.get(evento)

        if not configuracion:
            return Response(
                {
                    "detail": "El evento de auditoría no es válido."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        descripcion = configuracion["descripcion"]

        if referencia:
            descripcion = f"{descripcion} {referencia}"

        movimiento = MovimientoAuditoria.objects.create(
            usuario=request.user,
            sucursal=getattr(
                request.user,
                "sucursal",
                None,
            ),
            accion=configuracion["accion"],
            modulo=configuracion["modulo"],
            descripcion=descripcion,
        )

        serializer = MovimientoAuditoriaSerializer(
            movimiento
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
