from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets
from django.db.models.functions import TruncMonth
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    AsignacionVehiculo,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Mantenimiento,
    ConfiguracionSistema,
    Liquidacion,
    DetalleLiquidacion,
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
    AsignacionVehiculoSerializer,
    JornadaDiariaSerializer,
    GastoSerializer,
    AdelantoSerializer,
    MantenimientoSerializer,
    ConfiguracionSistemaSerializer,
    
)

from rest_framework.throttling import SimpleRateThrottle

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
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {
                    "detail": "Debes ingresar usuario y contraseña."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(
            request=request,
            username=username,
            password=password
        )

        if not user:
            return Response(
                {
                    "detail": "Usuario o contraseña incorrectos."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            return Response(
                {
                    "detail": "Este usuario está inactivo. Contacta al administrador."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.rol:
            return Response(
                {
                    "detail": "Este usuario no tiene un rol asignado."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if user.rol.codigo == "admin_sucursal" and not user.sucursal:
            return Response(
                {
                    "detail": "Este usuario no tiene una sucursal asignada."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Rota el token para invalidar credenciales antiguas robadas.
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response(
            {
                "token": token.key,
                "user": UsuarioSerializer(user).data,
                "rol": user.rol.codigo,
                "sucursal": user.sucursal.id if user.sucursal else None,
                "sucursal_nombre": user.sucursal.nombre if user.sucursal else None,
            },
            status=status.HTTP_200_OK
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

        qs = Conductor.objects.select_related(
            "sucursal",
            "usuario"
        ).all().order_by("-id")

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            if not user.sucursal:
                return qs.none()
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(usuario=user)

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

    @action(detail=True, methods=["post"], url_path="despedir",
            permission_classes=[EsAdminSucursalOSuperAdmin])
    def despedir(self, request, pk=None):
        conductor = self.get_object()
        user = request.user
        

        if es_admin_sucursal(user) and conductor.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes despedir conductores de otra sucursal.")

        conductor.activo = False
        conductor.save(update_fields=["activo"])

        # Libera el vehículo cerrando la asignación activa.
        asignacion = conductor.asignaciones.filter(activa=True).first()
        if asignacion:
            asignacion.activa = False
            asignacion.fecha_fin = timezone.localdate()
            asignacion.save(update_fields=["activa", "fecha_fin"])

        return Response(
            self.get_serializer(conductor).data,
            status=status.HTTP_200_OK
        )

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

        qs = Vehiculo.objects.select_related(
            "sucursal",
            "estado"
        ).all().order_by("placa")

        # El superadmin gestiona todas las sucursales: ve todos los vehículos
        # (globales y de sucursal), igual que los conductores.
        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            if not user.sucursal:
                return qs.none()
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()

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

        qs = AsignacionVehiculo.objects.select_related(
            "sucursal",
            "conductor",
            "vehiculo"
        ).all().order_by("-fecha_inicio")

        # El superadmin ve todas las asignaciones (de todas las sucursales).
        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            if not user.sucursal:
                return qs.none()
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(conductor__usuario=user)

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
            # El superadmin puede asignar en cualquier sucursal, pero el
            # conductor y el vehículo deben pertenecer a la misma (ambos
            # globales o ambos de la misma sucursal). La asignación hereda esa
            # sucursal.
            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise PermissionDenied(
                    "El conductor y el vehículo deben pertenecer a la misma sucursal."
                )

            self._guardar_validado(serializer, conductor.sucursal)
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

class JornadaDiariaViewSet(viewsets.ModelViewSet):
    serializer_class = JornadaDiariaSerializer

    def get_permissions(self):
        if self.action in [
            "update",
            "partial_update",
            "destroy",
            "registrar_ingreso",
        ]:
            return [EsAdminSucursalOSuperAdmin()]

        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        user = self.request.user

        qs = JornadaDiaria.objects.select_related(
            "sucursal",
            "estado",
            "conductor",
            "vehiculo"
        ).prefetch_related(
            "gastos",
            "adelantos"
        ).all()

        fecha = self.request.query_params.get("fecha")
        fecha_inicio = self.request.query_params.get("fecha_inicio")
        fecha_fin = self.request.query_params.get("fecha_fin")
        conductor_id = self.request.query_params.get("conductor")
        vehiculo_id = self.request.query_params.get("vehiculo")

        if es_superadmin(user):
            qs = qs.filter(sucursal__isnull=True)

        elif es_admin_sucursal(user):
            qs = qs.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            qs = qs.filter(conductor__usuario=user)

        else:
            return qs.none()

        if fecha:
            qs = qs.filter(fecha=fecha)

        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)

        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)

        if conductor_id:
            qs = qs.filter(conductor_id=conductor_id)

        if vehiculo_id:
            qs = qs.filter(vehiculo_id=vehiculo_id)

        return qs

    def _obtener_porcentaje_fallback(self, sucursal):
        # Fallback: % por defecto de la config de la sucursal (o global).
        configuracion = obtener_configuracion_sucursal(sucursal)
        return configuracion.porcentaje_pago_conductor

    def _resolver_porcentaje(self, conductor, sucursal):
        porcentaje = getattr(conductor, "porcentaje_pago", None)

        if porcentaje is None or porcentaje == "":
            porcentaje = self._obtener_porcentaje_fallback(sucursal)

        porcentaje = Decimal(str(porcentaje or "0.00"))

        if porcentaje < Decimal("1.00") or porcentaje > Decimal("100.00"):
            raise ValidationError({
                "porcentaje_pago": "El porcentaje del conductor debe estar entre 1 y 100."
            })

        return porcentaje.quantize(Decimal("0.01"))

    def perform_create(self, serializer):
        user = self.request.user

        conductor = serializer.validated_data.get("conductor")
        vehiculo = serializer.validated_data.get("vehiculo")

        if es_taxista(user):
            try:
                conductor = user.perfil_conductor
            except Conductor.DoesNotExist:
                raise ValidationError("Este usuario no tiene perfil de conductor.")

        if not conductor:
            raise ValidationError("Debes indicar el conductor.")

        if not vehiculo:
            raise ValidationError("Debes indicar el vehículo.")

        if es_superadmin(user):
            if conductor.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes registrar jornadas de conductores de sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes registrar jornadas de vehículos de sucursal desde el panel superadmin."
                )

            sucursal = None

        elif es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar jornadas para conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar jornadas para vehículos de otra sucursal.")

            sucursal = user.sucursal

        elif es_taxista(user):
            if conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes crear jornadas para otro conductor.")

            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise ValidationError("El conductor y el vehículo deben pertenecer al mismo entorno.")

            sucursal = conductor.sucursal

        else:
            raise PermissionDenied("No tienes permiso para crear jornadas.")

        asignacion_activa = AsignacionVehiculo.objects.filter(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            activa=True
        ).exists()

        if not asignacion_activa:
            raise ValidationError("El conductor no tiene una asignación activa con ese vehículo.")

        fecha = serializer.validated_data.get("fecha", timezone.localdate())

        jornada_existente = JornadaDiaria.objects.filter(
            fecha=fecha,
            conductor=conductor,
            vehiculo=vehiculo
        ).first()

        if jornada_existente:
            raise ValidationError({
                "detail": "Ya existe una jornada para este conductor y vehículo en esta fecha. Debes cerrar la jornada existente, no crear otra."
            })

        porcentaje = self._resolver_porcentaje(conductor, sucursal)

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            kilometraje_final=None,
            kilometros_recorridos=0,
            ingreso_bruto=Decimal("0.00"),
            monto_alquiler=Decimal("0.00"),
            tipo_cobro="porcentaje",
            porcentaje_pago_conductor=porcentaje,
            pago_conductor=Decimal("0.00"),
        )

        recalcular_totales_jornada(jornada)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        conductor = serializer.validated_data.get("conductor", instance.conductor)
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes modificar jornadas de sucursal desde el panel superadmin."
                )

            if conductor.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes usar conductores de sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes usar vehículos de sucursal desde el panel superadmin."
                )

            sucursal = None

        elif es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar jornadas de otra sucursal.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes usar conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes usar vehículos de otra sucursal.")

            sucursal = user.sucursal

        elif es_taxista(user):
            if instance.conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes modificar jornadas de otro conductor.")

            if conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes cambiar la jornada a otro conductor.")

            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise ValidationError("El conductor y el vehículo deben pertenecer al mismo entorno.")

            sucursal = conductor.sucursal

        else:
            raise PermissionDenied("No tienes permiso para modificar jornadas.")

        asignacion_activa = AsignacionVehiculo.objects.filter(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            activa=True
        ).exists()

        if not asignacion_activa:
            raise ValidationError("El conductor no tiene una asignación activa con ese vehículo.")

        porcentaje = self._resolver_porcentaje(conductor, sucursal)

        km_inicial = serializer.validated_data.get(
            "kilometraje_inicial",
            instance.kilometraje_inicial
        )

        km_final = serializer.validated_data.get(
            "kilometraje_final",
            instance.kilometraje_final
        )

        ingreso_bruto = serializer.validated_data.get(
            "ingreso_bruto",
            instance.ingreso_bruto
        )

        campos_calculados = calcular_campos_jornada(
            km_inicial,
            km_final,
            ingreso_bruto,
            porcentaje,
            serializer.validated_data.get("tipo_cobro", instance.tipo_cobro),
            serializer.validated_data.get("monto_alquiler", instance.monto_alquiler),
        )

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            porcentaje_pago_conductor=porcentaje,
            kilometros_recorridos=campos_calculados["kilometros_recorridos"],
            pago_conductor=campos_calculados["pago_conductor"]
        )

        actualizar_kilometraje_vehiculo(vehiculo, jornada.kilometraje_final)
        recalcular_totales_jornada(jornada)
    
    @action(detail=True, methods=["patch"], url_path="cerrar")
    def cerrar(self, request, pk=None):
        jornada = self.get_object()
        user = request.user

        kilometraje_final = request.data.get("kilometraje_final")
        ingreso_bruto = request.data.get("ingreso_bruto", jornada.ingreso_bruto)

        if kilometraje_final in [None, ""]:
            raise ValidationError({
                "kilometraje_final": "Debes ingresar el kilometraje final."
            })

        try:
            kilometraje_final = int(kilometraje_final)
        except (TypeError, ValueError):
            raise ValidationError({
                "kilometraje_final": "El kilometraje final debe ser un número válido."
            })

        if jornada.kilometraje_final is not None:
            raise ValidationError({
                "detail": "Esta jornada ya fue cerrada."
            })

        if kilometraje_final < jornada.kilometraje_inicial:
            raise ValidationError({
                "kilometraje_final": "El kilometraje final no puede ser menor al kilometraje inicial."
            })

        if es_taxista(user):
            if jornada.conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes cerrar una jornada de otro conductor.")

        elif es_admin_sucursal(user):
            if jornada.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes cerrar jornadas de otra sucursal.")

        elif es_superadmin(user):
            if jornada.sucursal_id is not None:
                raise PermissionDenied("No puedes cerrar jornadas de una sucursal desde el panel superadmin.")

        else:
            raise PermissionDenied("No tienes permiso para cerrar esta jornada.")

        porcentaje = self._resolver_porcentaje(jornada.conductor, jornada.sucursal)

        campos_calculados = calcular_campos_jornada(
            jornada.kilometraje_inicial,
            kilometraje_final,
            ingreso_bruto,
            porcentaje,
            jornada.tipo_cobro,
            jornada.monto_alquiler,
        )

        jornada.kilometraje_final = kilometraje_final
        jornada.ingreso_bruto = ingreso_bruto
        jornada.porcentaje_pago_conductor = porcentaje
        jornada.kilometros_recorridos = campos_calculados["kilometros_recorridos"]
        jornada.pago_conductor = campos_calculados["pago_conductor"]
        jornada.save()

        actualizar_kilometraje_vehiculo(jornada.vehiculo, jornada.kilometraje_final)
        recalcular_totales_jornada(jornada)

        serializer = self.get_serializer(jornada)
        return Response(serializer.data)
    
    @action(
        detail=True,
        methods=["patch"],
        url_path="registrar-ingreso",
        permission_classes=[EsAdminSucursalOSuperAdmin],
    )
    def registrar_ingreso(self, request, pk=None):
        jornada = self.get_object()
        user = request.user

        if not es_superadmin(user) and not es_admin_sucursal(user):
            raise PermissionDenied("Solo administración puede registrar el ingreso del día.")

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if jornada.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar ingresos de otra sucursal.")

        if es_superadmin(user):
            if jornada.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes registrar ingresos de una sucursal desde el panel superadmin."
                )

        tipo_cobro = request.data.get("tipo_cobro", jornada.tipo_cobro or "porcentaje")

        if tipo_cobro not in ["porcentaje", "alquiler"]:
            raise ValidationError({
                "tipo_cobro": "El tipo de cobro debe ser porcentaje o alquiler."
            })

        ingreso_bruto = _decimal(request.data.get("ingreso_bruto"))
        monto_alquiler = _decimal(request.data.get("monto_alquiler"))

        # Prioridad del %: body explicito > conductor.porcentaje_pago > config de sucursal.
               # El porcentaje siempre sale del conductor.
        # No se acepta porcentaje desde el frontend para evitar cálculos incorrectos.
        porcentaje = self._resolver_porcentaje(jornada.conductor, jornada.sucursal)

        if tipo_cobro == "porcentaje":
            if ingreso_bruto < 0:
                raise ValidationError({
                    "ingreso_bruto": "El ingreso del día no puede ser negativo."
                })

            jornada.ingreso_bruto = ingreso_bruto
            jornada.monto_alquiler = Decimal("0.00")
            jornada.porcentaje_pago_conductor = porcentaje

        if tipo_cobro == "alquiler":
            if monto_alquiler < 0:
                raise ValidationError({
                    "monto_alquiler": "El monto de alquiler no puede ser negativo."
                })

            jornada.ingreso_bruto = monto_alquiler
            jornada.monto_alquiler = monto_alquiler
            jornada.porcentaje_pago_conductor = Decimal("0.00")

        jornada.tipo_cobro = tipo_cobro

        if request.data.get("observaciones") is not None:
            jornada.observaciones = request.data.get("observaciones")

        campos_calculados = calcular_campos_jornada(
            jornada.kilometraje_inicial,
            jornada.kilometraje_final,
            jornada.ingreso_bruto,
            jornada.porcentaje_pago_conductor,
            jornada.tipo_cobro,
            jornada.monto_alquiler,
        )

        jornada.kilometros_recorridos = campos_calculados["kilometros_recorridos"]
        jornada.pago_conductor = campos_calculados["pago_conductor"]
        jornada.ingreso_bruto = campos_calculados["ingreso_bruto"]

        jornada.save()
        recalcular_totales_jornada(jornada)

        serializer = self.get_serializer(jornada)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        qs = Mantenimiento.objects.select_related(
            "sucursal",
            "vehiculo",
            "tipo_mantenimiento",
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
                    "No puedes registrar mantenimiento de vehículos de una sucursal desde el panel superadmin."
                )

            mantenimiento = serializer.save(
                sucursal=None,
                vehiculo=vehiculo
            )
            aplicar_mantenimiento_en_vehiculo(mantenimiento)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes registrar mantenimiento para vehículos de otra sucursal."
                )

            mantenimiento = serializer.save(
                sucursal=user.sucursal,
                vehiculo=vehiculo
            )
            aplicar_mantenimiento_en_vehiculo(mantenimiento)
            return

        raise PermissionDenied("No tienes permiso para registrar mantenimiento.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if not vehiculo:
            raise ValidationError("Debes indicar el vehículo.")

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes modificar mantenimiento de una sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes mover este mantenimiento a un vehículo de sucursal."
                )

            mantenimiento = serializer.save(
                sucursal=None,
                vehiculo=vehiculo
            )
            aplicar_mantenimiento_en_vehiculo(mantenimiento)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes modificar mantenimiento de otra sucursal."
                )

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes asignar mantenimiento a vehículos de otra sucursal."
                )

            mantenimiento = serializer.save(
                sucursal=user.sucursal,
                vehiculo=vehiculo
            )
            aplicar_mantenimiento_en_vehiculo(mantenimiento)
            return

        raise PermissionDenied("No tienes permiso para modificar mantenimiento.")

    def perform_destroy(self, instance):
        user = self.request.user

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes eliminar mantenimiento de una sucursal desde el panel superadmin."
                )

        elif es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied(
                    "No puedes eliminar mantenimiento de otra sucursal."
                )

        else:
            raise PermissionDenied("No tienes permiso para eliminar mantenimiento.")

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
    permission_classes = [EsAdminSucursalOSuperAdmin]

    def get(self, request):
        user = request.user
        periodo = request.query_params.get("periodo", "dia")
        fecha_inicio, fecha_fin = obtener_rango_periodo(periodo)

        jornadas = JornadaDiaria.objects.all()
        gastos = Gasto.objects.all()
        mantenimientos = Mantenimiento.objects.all()

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")

            if sucursal_id:
                jornadas = jornadas.filter(sucursal_id=sucursal_id)
                gastos = gastos.filter(sucursal_id=sucursal_id)
                mantenimientos = mantenimientos.filter(sucursal_id=sucursal_id)
            else:
                jornadas = jornadas.filter(sucursal__isnull=True)
                gastos = gastos.filter(sucursal__isnull=True)
                mantenimientos = mantenimientos.filter(sucursal__isnull=True)

        elif es_admin_sucursal(user):
            if not user.sucursal:
                return Response(
                    {"detail": "Tu usuario no tiene una sucursal asignada."},
                    status=403
                )

            jornadas = jornadas.filter(sucursal=user.sucursal)
            gastos = gastos.filter(sucursal=user.sucursal)
            mantenimientos = mantenimientos.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            jornadas = jornadas.filter(
                sucursal=user.sucursal,
                conductor__usuario=user
            )
            gastos = Gasto.objects.none()
            mantenimientos = Mantenimiento.objects.none()

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        jornadas = jornadas.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        gastos = gastos.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        mantenimientos = mantenimientos.filter(
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )

        total_ingresos = sumar_decimal(jornadas, "ingreso_bruto")
        total_pago_conductores = sumar_decimal(jornadas, "pago_conductor")
        total_adelantos = sumar_decimal(jornadas, "total_adelantos")
        total_ganancia_dueno = sumar_decimal(jornadas, "ganancia_dueno")

        total_gastos_vehiculos = sumar_decimal(gastos, "monto")
        total_mantenimiento = sumar_decimal(mantenimientos, "costo")
        total_gastos_operativos = total_gastos_vehiculos + total_mantenimiento

        total_ganancia_real_dueno = (
            total_ganancia_dueno
            - total_gastos_vehiculos
            - total_mantenimiento
        )

        data = {
            "periodo": periodo,
            "fecha_inicio": str(fecha_inicio),
            "fecha_fin": str(fecha_fin),

            "total_ingresos": total_ingresos,
            "total_pago_conductores": total_pago_conductores,
            "total_adelantos": total_adelantos,

            "total_ganancia_dueno": total_ganancia_dueno,

            "total_gastos_vehiculos": total_gastos_vehiculos,
            "total_mantenimiento": total_mantenimiento,
            "total_gastos_operativos": total_gastos_operativos,

            "total_ganancia_real_dueno": total_ganancia_real_dueno,

            "total_gastos": total_gastos_operativos,
            "total_jornadas": jornadas.count(),
            "total_registros_gastos": gastos.count(),
            "total_registros_mantenimiento": mantenimientos.count(),
        }

        return Response(data)


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
            sucursal_id = request.query_params.get("sucursal")
            if sucursal_id:
                vehiculos = vehiculos.filter(sucursal_id=sucursal_id)
                conductores = conductores.filter(sucursal_id=sucursal_id)

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

            ganancia_real = ingresos_data["ganancia_base"] - gastos_operativos

            if ganancia_real < Decimal("0.00"):
                ganancia_real = Decimal("0.00")

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
        "id": liquidacion.id,
        "conductor": {
            "id": liquidacion.conductor_id,
            "nombre": f"{liquidacion.conductor.nombre} {liquidacion.conductor.apellido}".strip(),
            "cedula": liquidacion.conductor.cedula,
        },
        "conductor_nombre": f"{liquidacion.conductor.nombre} {liquidacion.conductor.apellido}".strip(),
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


def _obtener_jornadas_pendientes_liquidacion(user, conductor):
    jornadas = JornadaDiaria.objects.select_related(
        "conductor",
        "vehiculo",
        "sucursal"
    ).filter(
        conductor=conductor,
        kilometraje_final__isnull=False,
        pago_pendiente_conductor__gt=Decimal("0.00")
    ).order_by("fecha", "id")

    if es_superadmin(user):
        if conductor.sucursal_id is None:
            jornadas = jornadas.filter(sucursal__isnull=True)
        else:
            jornadas = jornadas.filter(sucursal=conductor.sucursal)

    elif es_admin_sucursal(user):
        jornadas = jornadas.filter(sucursal=user.sucursal)

    elif es_taxista(user):
        jornadas = jornadas.filter(conductor__usuario=user)

    else:
        jornadas = JornadaDiaria.objects.none()

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