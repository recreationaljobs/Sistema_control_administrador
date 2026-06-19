from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import status, viewsets
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
    LiquidacionConductor,
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
    LiquidacionConductorSerializer,
)

from .permissions import (
    EsSuperAdmin,
    EsAdminSucursalOSuperAdmin,
    EstaAutenticado,
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
    sumar_decimal,
    sumar_entero,
)

CODIGOS_ADELANTO = ["adelanto", "anticipo"]
CODIGOS_ABONO = ["abono", "abonado"]


def q_estado_codigos(codigos):
    q = Q()

    for codigo in codigos:
        q |= Q(estado__codigo__iexact=codigo)

    return q


def es_estado_abono(estado):
    if not estado:
        return False

    return estado.codigo.lower() in CODIGOS_ABONO


def es_estado_adelanto(estado):
    if not estado:
        return False

    return estado.codigo.lower() in CODIGOS_ADELANTO


def obtener_estado_por_tipo(tipo):
    tipo = (tipo or "").upper()

    if tipo == "ABONO":
        return EstadoAdelanto.objects.filter(
            Q(codigo__iexact="abono") |
            Q(codigo__iexact="abonado")
        ).first()

    return EstadoAdelanto.objects.filter(
        Q(codigo__iexact="adelanto") |
        Q(codigo__iexact="anticipo")
    ).first()

def obtener_tipo_desde_estado(estado):
    if not estado:
        return "ADELANTO"

    codigo = estado.codigo.lower()

    if codigo in CODIGOS_ABONO:
        return "ABONO"

    return "ADELANTO"


def obtener_tipo_display_desde_estado(estado):
    if not estado:
        return "Movimiento"

    codigo = estado.codigo.lower()

    if codigo in ["abono", "abonado"]:
        return "Abono"

    if codigo == "anticipo":
        return "Anticipo"

    return "Adelanto"
def obtener_sucursal_por_rol(user, conductor=None):
    if not conductor:
        raise ValidationError("Debes seleccionar un conductor.")

    if es_superadmin(user):
        return conductor.sucursal  # Puede ser None. Eso significa entorno super_admin.

    if es_admin_sucursal(user):
        if not user.sucursal:
            raise ValidationError("Tu usuario no tiene una sucursal asignada.")

        if conductor.sucursal_id != user.sucursal_id:
            raise PermissionDenied(
                "No puedes registrar movimientos para un conductor de otra sucursal."
            )

        return user.sucursal

    if es_taxista(user):
        try:
            perfil = user.perfil_conductor
        except Conductor.DoesNotExist:
            raise ValidationError("Este usuario no tiene perfil de conductor.")

        if conductor.id != perfil.id:
            raise PermissionDenied("No puedes consultar información de otro conductor.")

        return perfil.sucursal  # También puede ser None si es entorno super_admin.

    raise PermissionDenied("No tienes permiso para realizar esta acción.")

def calcular_saldo_adelantos(conductor, sucursal):
    qs = Adelanto.objects.filter(
        conductor=conductor,
        sucursal=sucursal
    )

    total_adelantos = qs.filter(
        q_estado_codigos(CODIGOS_ADELANTO)
    ).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0.00")

    total_abonos = qs.filter(
        q_estado_codigos(CODIGOS_ABONO)
    ).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0.00")

    pendiente = total_adelantos - total_abonos

    if pendiente < Decimal("0.00"):
        pendiente = Decimal("0.00")

    return {
        "total_adelantos": total_adelantos,
        "total_abonos": total_abonos,
        "saldo_pendiente": pendiente,
    }

class LoginView(APIView):
    permission_classes = [AllowAny]

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
            request,
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

        token, created = Token.objects.get_or_create(user=user)

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


class MiPerfilView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(
            UsuarioSerializer(request.user).data,
            status=status.HTTP_200_OK
        )
    

class SucursalViewSet(viewsets.ModelViewSet):
    serializer_class = SucursalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [EstaAutenticado()]

        return [EsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user

        qs = Sucursal.objects.all().order_by("nombre")

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            if not user.sucursal:
                return qs.none()

            return qs.filter(id=user.sucursal_id)

        if es_taxista(user):
            conductor = getattr(user, "perfil_conductor", None)

            if conductor and conductor.sucursal_id:
                return qs.filter(id=conductor.sucursal_id)

            return qs.none()

        return qs.none()

class RolViewSet(viewsets.ModelViewSet):
    serializer_class = RolSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [EstaAutenticado()]

        return [EsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user

        queryset = Rol.objects.all().order_by("nombre")

        if es_superadmin(user):
            return queryset

        if es_admin_sucursal(user):
            return queryset.filter(codigo="taxista")

        return Rol.objects.none()

class CatalogoProtegidoMixin:
    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsAdminSucursalOSuperAdmin()]


class EstadoVehiculoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = EstadoVehiculo.objects.all().order_by("nombre")
    serializer_class = EstadoVehiculoSerializer


class EstadoJornadaViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = EstadoJornada.objects.all().order_by("nombre")
    serializer_class = EstadoJornadaSerializer


class TipoGastoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = TipoGasto.objects.all().order_by("nombre")
    serializer_class = TipoGastoSerializer


class EstadoGastoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = EstadoGasto.objects.all().order_by("nombre")
    serializer_class = EstadoGastoSerializer


class EstadoAdelantoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = EstadoAdelanto.objects.all().order_by("nombre")
    serializer_class = EstadoAdelantoSerializer


class TipoMantenimientoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = TipoMantenimiento.objects.all().order_by("nombre")
    serializer_class = TipoMantenimientoSerializer


class EstadoMantenimientoViewSet(CatalogoProtegidoMixin, viewsets.ModelViewSet):
    queryset = EstadoMantenimiento.objects.all().order_by("nombre")
    serializer_class = EstadoMantenimientoSerializer

class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "me"]:
            return [EstaAutenticado()]

        return [EsAdminSucursalOSuperAdmin()]

    def get_queryset(self):
        user = self.request.user

        queryset = Usuario.objects.select_related(
            "rol",
            "sucursal"
        ).all().order_by("-id")

        if es_superadmin(user):
            return queryset.filter(
                Q(sucursal__isnull=True) |
                Q(rol__codigo="admin_sucursal")
            )

        if es_admin_sucursal(user):
            return queryset.filter(
                sucursal=user.sucursal
            ).exclude(
                rol__codigo__in=["superadmin", "super_admin", "usuario_sistema", "admin_sucursal"]
            )

        if es_taxista(user):
            return queryset.filter(id=user.id)

        return queryset.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=False, methods=["get"], permission_classes=[EstaAutenticado])
    def me(self, request):
        return Response(self.get_serializer(request.user).data)

    def perform_create(self, serializer):
        user = self.request.user
        rol = serializer.validated_data.get("rol")

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if not rol or rol.codigo != "taxista":
                raise PermissionDenied("Un administrador de sucursal solo puede crear usuarios taxistas.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear usuarios.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        rol = serializer.validated_data.get("rol", instance.rol)

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar usuarios de otra sucursal.")

            if not rol or rol.codigo != "taxista":
                raise PermissionDenied("Un administrador de sucursal solo puede modificar usuarios taxistas.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar usuarios.")


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
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(usuario=user)

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

        raise PermissionDenied("No tienes permiso para crear conductores.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if es_superadmin(user):
            sucursal = serializer.validated_data.get("sucursal", instance.sucursal)

            if not sucursal:
                raise ValidationError("Debes seleccionar la sucursal del conductor.")

            serializer.save(sucursal=sucursal)
            return
        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar conductores de otra sucursal.")

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

        if es_superadmin(user):
             pass

        elif es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            qs = qs.filter(sucursal=user.sucursal)

        else:
            return Response([])

        if search:
            qs = (
                qs.filter(nombre__icontains=search)
                | qs.filter(apellido__icontains=search)
                | qs.filter(cedula__icontains=search)
            )

            if es_superadmin(user):
                qs = qs.filter(sucursal__isnull=True)

            if es_admin_sucursal(user):
                qs = qs.filter(sucursal=user.sucursal)

        serializer = self.get_serializer(qs.distinct(), many=True)
        return Response(serializer.data)

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

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
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
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes modificar vehículos de una sucursal desde el panel superadmin."
                )

            serializer.save(sucursal=None)
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar vehículos de otra sucursal.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar vehículos.")

class AsignacionVehiculoViewSet(viewsets.ModelViewSet):
    serializer_class = AsignacionVehiculoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [EstaAutenticado()]

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

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(conductor__usuario=user)

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        conductor = serializer.validated_data.get("conductor")
        vehiculo = serializer.validated_data.get("vehiculo")

        if es_superadmin(user):
            if conductor.sucursal_id is not None or vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes asignar conductores o vehículos de sucursal desde el panel superadmin."
                )

            serializer.save(sucursal=None)
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar vehículos de otra sucursal.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear asignaciones.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        conductor = serializer.validated_data.get("conductor", instance.conductor)
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if es_superadmin(user):
            if instance.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes modificar asignaciones de sucursal desde el panel superadmin."
                )

            if conductor.sucursal_id is not None or vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes usar conductores o vehículos de sucursal desde el panel superadmin."
                )

            serializer.save(sucursal=None)
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar asignaciones de otra sucursal.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar conductores de otra sucursal.")

            if vehiculo.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar vehículos de otra sucursal.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar asignaciones.")


class JornadaDiariaViewSet(viewsets.ModelViewSet):
    serializer_class = JornadaDiariaSerializer

    def get_permissions(self):
        if self.action == "destroy":
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
        ).all()

        fecha = self.request.query_params.get("fecha")
        fecha_inicio = self.request.query_params.get("fecha_inicio")
        fecha_fin = self.request.query_params.get("fecha_fin")
        conductor_id = self.request.query_params.get("conductor")
        vehiculo_id = self.request.query_params.get("vehiculo")

        if es_superadmin(user):
            pass

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

    def _obtener_porcentaje(self, sucursal):
        configuracion = obtener_configuracion_sucursal(sucursal)
        return configuracion.porcentaje_pago_conductor

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

        porcentaje = self._obtener_porcentaje(sucursal)

        kilometraje_inicial = serializer.validated_data.get("kilometraje_inicial")
        kilometraje_final = serializer.validated_data.get("kilometraje_final")
        ingreso_bruto = serializer.validated_data.get("ingreso_bruto") or Decimal("0.00")

        if kilometraje_final is None:
            jornada = serializer.save(
                sucursal=sucursal,
                conductor=conductor,
                vehiculo=vehiculo,
                kilometraje_inicial=kilometraje_inicial,
                kilometraje_final=None,
                ingreso_bruto=ingreso_bruto,
                porcentaje_pago_conductor=porcentaje,
                kilometros_recorridos=0,
                pago_conductor=Decimal("0.00")
            )

            recalcular_totales_jornada(jornada)
            return

        campos_calculados = calcular_campos_jornada(
            kilometraje_inicial,
            kilometraje_final,
            ingreso_bruto,
            porcentaje
        )

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            kilometraje_inicial=kilometraje_inicial,
            kilometraje_final=kilometraje_final,
            ingreso_bruto=ingreso_bruto,
            porcentaje_pago_conductor=porcentaje,
            kilometros_recorridos=campos_calculados["kilometros_recorridos"],
            pago_conductor=campos_calculados["pago_conductor"]
        )

        actualizar_kilometraje_vehiculo(vehiculo, jornada.kilometraje_final)
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

        porcentaje = self._obtener_porcentaje(sucursal)

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
            porcentaje
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

        if es_taxista(user):
            if jornada.conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes cerrar una jornada de otro conductor.")

        elif es_admin_sucursal(user):
            if jornada.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes cerrar jornadas de otra sucursal.")

        elif es_superadmin(user):
            pass

        else:
            raise PermissionDenied("No tienes permiso para cerrar jornadas.")

        if jornada.kilometraje_final is not None:
            raise ValidationError({
                "detail": "Esta jornada ya fue cerrada."
            })

        kilometraje_final = request.data.get("kilometraje_final")

        if kilometraje_final in [None, ""]:
            raise ValidationError({
                "kilometraje_final": "Debes ingresar el kilometraje final."
            })

        try:
            kilometraje_final = int(kilometraje_final)
        except ValueError:
            raise ValidationError({
                "kilometraje_final": "El kilometraje final debe ser un número válido."
            })

        if kilometraje_final < jornada.kilometraje_inicial:
            raise ValidationError({
                "kilometraje_final": "El kilometraje final no puede ser menor al kilometraje inicial."
            })

        porcentaje = self._obtener_porcentaje(jornada.sucursal)

        campos_calculados = calcular_campos_jornada(
            jornada.kilometraje_inicial,
            kilometraje_final,
            jornada.ingreso_bruto or Decimal("0.00"),
            porcentaje
        )

        jornada.kilometraje_final = kilometraje_final
        jornada.porcentaje_pago_conductor = porcentaje
        jornada.kilometros_recorridos = campos_calculados["kilometros_recorridos"]
        jornada.pago_conductor = campos_calculados["pago_conductor"]

        observaciones = request.data.get("observaciones")
        if observaciones is not None:
            jornada.observaciones = observaciones

        jornada.save()

        actualizar_kilometraje_vehiculo(jornada.vehiculo, jornada.kilometraje_final)
        recalcular_totales_jornada(jornada)

        serializer = self.get_serializer(jornada)
        return Response(serializer.data)


    @action(detail=True, methods=["patch"], url_path="registrar-ingreso")
    def registrar_ingreso(self, request, pk=None):
        jornada = self.get_object()
        user = request.user

        if es_taxista(user):
            raise PermissionDenied(
                "El taxista no puede registrar el ingreso del día. Solo puede iniciar y cerrar jornada."
            )

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if jornada.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar ingresos de otra sucursal.")

        elif es_superadmin(user):
            pass

        else:
            raise PermissionDenied("No tienes permiso para registrar ingresos.")

        if jornada.kilometraje_final is None:
            raise ValidationError({
                "kilometraje_final": "Primero debes cerrar la jornada con el kilometraje final."
            })

        tipo_cobro = request.data.get("tipo_cobro") or "porcentaje"

        if tipo_cobro not in ["porcentaje", "alquiler"]:
            raise ValidationError({
                "tipo_cobro": "El tipo de cobro debe ser porcentaje o alquiler."
            })

        ingreso_bruto = Decimal(
            str(request.data.get("ingreso_bruto", "0.00") or "0.00")
        )

        monto_alquiler = Decimal(
            str(request.data.get("monto_alquiler", "0.00") or "0.00")
        )

        porcentaje = Decimal(
            str(request.data.get("porcentaje_pago_conductor", "30.00") or "30.00")
        )

        if tipo_cobro == "porcentaje":
            if ingreso_bruto < Decimal("0.00"):
                raise ValidationError({
                    "ingreso_bruto": "El ingreso del día no puede ser negativo."
                })

            if porcentaje < Decimal("0.00") or porcentaje > Decimal("100.00"):
                raise ValidationError({
                    "porcentaje_pago_conductor": "El porcentaje debe estar entre 0 y 100."
                })

            jornada.ingreso_bruto = ingreso_bruto
            jornada.porcentaje_pago_conductor = porcentaje
            jornada.pago_conductor = (ingreso_bruto * porcentaje) / Decimal("100.00")

            if hasattr(jornada, "tipo_cobro"):
                jornada.tipo_cobro = "porcentaje"

            if hasattr(jornada, "monto_alquiler"):
                jornada.monto_alquiler = Decimal("0.00")

        elif tipo_cobro == "alquiler":
            if monto_alquiler < Decimal("0.00"):
                raise ValidationError({
                    "monto_alquiler": "El monto de alquiler no puede ser negativo."
                })

            jornada.ingreso_bruto = monto_alquiler
            jornada.porcentaje_pago_conductor = Decimal("0.00")
            jornada.pago_conductor = Decimal("0.00")

            if hasattr(jornada, "tipo_cobro"):
                jornada.tipo_cobro = "alquiler"

            if hasattr(jornada, "monto_alquiler"):
                jornada.monto_alquiler = monto_alquiler

        jornada.kilometros_recorridos = (
            jornada.kilometraje_final - jornada.kilometraje_inicial
        )

        observaciones = request.data.get("observaciones")
        if observaciones is not None:
            jornada.observaciones = observaciones

        jornada.save()
        recalcular_totales_jornada(jornada)

        serializer = self.get_serializer(jornada)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GastoViewSet(viewsets.ModelViewSet):
    serializer_class = GastoSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Gasto.objects.select_related(
            "sucursal",
            "jornada",
            "vehiculo",
            "conductor",
            "tipo_gasto",
            "estado"
        ).all()

        fecha = self.request.query_params.get("fecha")
        fecha_inicio = self.request.query_params.get("fecha_inicio")
        fecha_fin = self.request.query_params.get("fecha_fin")

        if es_superadmin(user):
            pass
        elif es_admin_sucursal(user):
            qs = qs.filter(sucursal=user.sucursal)
        elif es_taxista(user):
            qs = qs.filter(sucursal=user.sucursal, conductor__usuario=user)
        else:
            return qs.none()

        if fecha:
            qs = qs.filter(fecha=fecha)

        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)

        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        jornada = serializer.validated_data.get("jornada")

        if not jornada:
            vehiculo = serializer.validated_data.get("vehiculo")
            conductor = serializer.validated_data.get("conductor")
            sucursal = vehiculo.sucursal if vehiculo else None
        else:
            vehiculo = jornada.vehiculo
            conductor = jornada.conductor
            sucursal = jornada.sucursal

        if not sucursal:
            raise ValidationError("No se pudo determinar la sucursal del gasto.")

        if es_admin_sucursal(user) and sucursal.id != user.sucursal_id:
            raise PermissionDenied("No puedes registrar gastos en otra sucursal.")

        if es_taxista(user):
            try:
                perfil = user.perfil_conductor
            except Conductor.DoesNotExist:
                raise ValidationError("Este usuario no tiene perfil de conductor.")

            if conductor and conductor.id != perfil.id:
                raise PermissionDenied("No puedes registrar gastos para otro conductor.")

        gasto = serializer.save(
            sucursal=sucursal,
            vehiculo=vehiculo,
            conductor=conductor
        )

        if gasto.jornada:
            recalcular_totales_jornada(gasto.jornada)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_admin_sucursal(user) and instance.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes modificar gastos de otra sucursal.")

        if es_taxista(user) and instance.conductor and instance.conductor.usuario_id != user.id:
            raise PermissionDenied("No puedes modificar gastos de otro conductor.")

        gasto = serializer.save()

        if gasto.jornada:
            recalcular_totales_jornada(gasto.jornada)

    def perform_destroy(self, instance):
        jornada = instance.jornada
        instance.delete()

        if jornada:
            recalcular_totales_jornada(jornada)


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
            "conductor",
            "estado"
        ).all().order_by("-fecha", "-id")

        conductor_id = self.request.query_params.get("conductor")
        tipo = self.request.query_params.get("tipo")
        fecha_inicio = self.request.query_params.get("fecha_inicio")
        fecha_fin = self.request.query_params.get("fecha_fin")

        if es_superadmin(user):
            pass

        elif es_admin_sucursal(user):
            qs = qs.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            qs = qs.filter(conductor__usuario=user)

        else:
            return qs.none()

        if conductor_id:
            qs = qs.filter(conductor_id=conductor_id)

        if tipo:
            tipo = tipo.upper()

            if tipo == "ABONO":
                qs = qs.filter(q_estado_codigos(CODIGOS_ABONO))

            elif tipo == "ADELANTO":
                qs = qs.filter(q_estado_codigos(CODIGOS_ADELANTO))

        if fecha_inicio:
            qs = qs.filter(fecha__gte=fecha_inicio)

        if fecha_fin:
            qs = qs.filter(fecha__lte=fecha_fin)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        conductor = serializer.validated_data.get("conductor")
        estado = serializer.validated_data.get("estado")
        monto = serializer.validated_data.get("monto")
        tipo_recibido = self.request.data.get("tipo")

        if not conductor:
            raise ValidationError("Debes seleccionar un conductor.")

        if es_taxista(user):
            raise PermissionDenied("El taxista no puede registrar adelantos o abonos.")

        sucursal = obtener_sucursal_por_rol(user, conductor)


        if not estado:
            estado = obtener_estado_por_tipo(tipo_recibido)

        if not estado:
            raise ValidationError(
                "Debes seleccionar un estado válido para el movimiento."
            )

        es_abono = es_estado_abono(estado)

        if es_abono:
            saldo = calcular_saldo_adelantos(conductor, sucursal)

            if saldo["saldo_pendiente"] <= Decimal("0.00"):
                raise ValidationError(
                    "Este conductor no tiene saldo pendiente de adelantos."
                )

            if monto > saldo["saldo_pendiente"]:
                raise ValidationError(
                    "El abono no puede ser mayor al saldo pendiente."
                )

        serializer.save(
            sucursal=sucursal,
            estado=estado
        )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        conductor = serializer.validated_data.get("conductor", instance.conductor)
        estado = serializer.validated_data.get("estado", instance.estado)
        monto = serializer.validated_data.get("monto", instance.monto)

        sucursal = obtener_sucursal_por_rol(user, conductor)

        if es_taxista(user):
            raise PermissionDenied("El taxista no puede modificar adelantos o abonos.")

        if instance.sucursal_id != (sucursal.id if sucursal else None):
            raise PermissionDenied("No puedes modificar movimientos de otro entorno.")

        if estado and es_estado_abono(estado):
            saldo = calcular_saldo_adelantos(conductor, sucursal)

            saldo_actual = saldo["saldo_pendiente"]

            if instance.estado and es_estado_abono(instance.estado):
                saldo_actual += instance.monto

            if monto > saldo_actual:
                raise ValidationError(
                    "El abono no puede ser mayor al saldo pendiente."
                )

        serializer.save(
            sucursal=sucursal,
            estado=estado
        )

    @action(detail=False, methods=["get"], url_path="resumen-conductor")
    def resumen_conductor(self, request):
        conductor_id = request.query_params.get("conductor_id")

        if not conductor_id:
            return Response(
                {"detail": "conductor_id es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conductor = Conductor.objects.select_related("sucursal", "usuario").get(id=conductor_id)
        except Conductor.DoesNotExist:
            return Response(
                {"detail": "El conductor no existe."},
                status=status.HTTP_404_NOT_FOUND
            )

        sucursal = obtener_sucursal_por_rol(request.user, conductor)

        qs = Adelanto.objects.select_related(
            "sucursal",
            "conductor",
            "estado"
        ).filter(
            conductor=conductor,
            sucursal=sucursal
        ).order_by("-fecha", "-id")

        saldo = calcular_saldo_adelantos(conductor, sucursal)

        return Response({
            "conductor": {
                "id": conductor.id,
                "nombre": f"{conductor.nombre} {conductor.apellido}".strip(),
                "cedula": conductor.cedula,
            },
            "total_adelantos": saldo["total_adelantos"],
            "total_abonos": saldo["total_abonos"],
            "saldo_pendiente": saldo["saldo_pendiente"],
            "historial": AdelantoSerializer(qs, many=True).data,
        })

    @action(detail=True, methods=["get"], url_path="recibo")
    def recibo(self, request, pk=None):
        adelanto = self.get_object()

        return Response({
            "id": adelanto.id,
            "tipo": obtener_tipo_desde_estado(adelanto.estado),
            "tipo_display": obtener_tipo_display_desde_estado(adelanto.estado),
            "monto": adelanto.monto,
            "fecha": adelanto.fecha,
            "observacion": adelanto.observacion or "",
            "estado": {
                "id": adelanto.estado.id,
                "nombre": adelanto.estado.nombre,
                "codigo": adelanto.estado.codigo,
            } if adelanto.estado else None,
            "sucursal": {
                "id": adelanto.sucursal.id,
                "nombre": adelanto.sucursal.nombre,
            } if adelanto.sucursal else None,
            "conductor": {
                "id": adelanto.conductor.id,
                "nombre": f"{adelanto.conductor.nombre} {adelanto.conductor.apellido}".strip(),
                "cedula": adelanto.conductor.cedula,
            } if adelanto.conductor else None,
        })


class LiquidacionConductorViewSet(viewsets.ModelViewSet):
    serializer_class = LiquidacionConductorSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]

        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        qs = LiquidacionConductor.objects.select_related(
            "conductor",
            "sucursal"
        ).all().order_by("-fecha_creacion", "-id")

        conductor_id = self.request.query_params.get("conductor")

        if es_superadmin(user):
            pass

        elif es_admin_sucursal(user):
            qs = qs.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            qs = qs.filter(conductor__usuario=user)

        else:
            return qs.none()

        if conductor_id:
            qs = qs.filter(conductor_id=conductor_id)

        return qs

    def _obtener_conductor_y_sucursal(self, user, conductor_id):
        if not conductor_id:
            raise ValidationError("Debes seleccionar un conductor.")

        try:
            conductor = Conductor.objects.select_related(
                "sucursal",
                "usuario"
            ).get(id=conductor_id)
        except Conductor.DoesNotExist:
            raise ValidationError("El conductor no existe.")

        if es_superadmin(user):
            sucursal = conductor.sucursal
            return conductor, sucursal

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes liquidar conductores de otra sucursal.")

            return conductor, user.sucursal

        if es_taxista(user):
            if conductor.usuario_id != user.id:
                raise PermissionDenied("No puedes consultar liquidaciones de otro conductor.")

            return conductor, conductor.sucursal

        raise PermissionDenied("No tienes permiso para realizar esta acción.")

    def _jornadas_pendientes(self, conductor, sucursal):
        return JornadaDiaria.objects.select_related(
            "vehiculo",
            "estado"
        ).filter(
            conductor=conductor,
            sucursal=sucursal,
            liquidacion__isnull=True
        ).order_by("fecha", "id")

    @action(detail=False, methods=["get"], url_path="preview")
    def preview(self, request):
        conductor_id = request.query_params.get("conductor_id")

        conductor, sucursal = self._obtener_conductor_y_sucursal(
            request.user,
            conductor_id
        )

        jornadas = self._jornadas_pendientes(conductor, sucursal)

        total_jornadas = jornadas.aggregate(
            total=Sum("pago_conductor")
        )["total"] or Decimal("0.00")

        primera_jornada = jornadas.first()
        ultima_jornada = jornadas.last()

        fecha_inicio = primera_jornada.fecha if primera_jornada else None
        fecha_fin = ultima_jornada.fecha if ultima_jornada else None

        saldo = calcular_saldo_adelantos(conductor, sucursal)
        pendiente_adelantos = saldo["saldo_pendiente"]

        movimientos_adelantos = Adelanto.objects.select_related(
            "estado",
            "conductor",
            "sucursal"
        ).filter(
            conductor=conductor,
            sucursal=sucursal
        ).order_by("-fecha", "-id")

        return Response({
            "conductor": {
                "id": conductor.id,
                "nombre": f"{conductor.nombre} {conductor.apellido}".strip(),
                "cedula": conductor.cedula,
            },
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "jornadas_count": jornadas.count(),
            "total_jornadas": total_jornadas,
            "total_adelantos": saldo["total_adelantos"],
            "total_abonos": saldo["total_abonos"],
            "pendiente_adelantos": pendiente_adelantos,
            "total_sugerido": total_jornadas,
            "jornadas": [
                {
                    "id": jornada.id,
                    "fecha": jornada.fecha,
                    "vehiculo": jornada.vehiculo.placa if jornada.vehiculo else "",
                    "kilometros_recorridos": jornada.kilometros_recorridos,
                    "ingreso_bruto": jornada.ingreso_bruto,
                    "pago_conductor": jornada.pago_conductor,
                    "estado": jornada.estado.nombre if jornada.estado else "",
                }
                for jornada in jornadas
            ],
            "historial_adelantos": AdelantoSerializer(
                movimientos_adelantos,
                many=True
            ).data,
        })

    def perform_create(self, serializer):
        user = self.request.user
        conductor = serializer.validated_data.get("conductor")
        abono_aplicado = serializer.validated_data.get(
            "abono_aplicado",
            Decimal("0.00")
        )
        ajuste_manual = serializer.validated_data.get(
            "ajuste_manual",
            Decimal("0.00")
        )

        conductor, sucursal = self._obtener_conductor_y_sucursal(
            user,
            conductor.id if conductor else None
        )

        if es_taxista(user):
            raise PermissionDenied("El taxista no puede registrar liquidaciones.")

        jornadas = self._jornadas_pendientes(conductor, sucursal)

        if not jornadas.exists():
            raise ValidationError("Este conductor no tiene jornadas pendientes de liquidar.")

        total_jornadas = jornadas.aggregate(
            total=Sum("pago_conductor")
        )["total"] or Decimal("0.00")

        primera_jornada = jornadas.first()
        ultima_jornada = jornadas.last()

        saldo = calcular_saldo_adelantos(conductor, sucursal)
        pendiente_adelantos = saldo["saldo_pendiente"]

        if abono_aplicado > pendiente_adelantos:
            raise ValidationError("El abono aplicado no puede ser mayor al saldo pendiente.")

        if abono_aplicado > (total_jornadas + ajuste_manual):
            raise ValidationError("El abono aplicado no puede ser mayor al total disponible para pagar.")

        total_pago = total_jornadas - abono_aplicado + ajuste_manual

        if total_pago < Decimal("0.00"):
            total_pago = Decimal("0.00")

        liquidacion = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
            fecha_inicio=primera_jornada.fecha,
            fecha_fin=ultima_jornada.fecha,
            total_jornadas=total_jornadas,
            total_adelantos_pendientes=pendiente_adelantos,
            abono_aplicado=abono_aplicado,
            ajuste_manual=ajuste_manual,
            total_pago=total_pago,
        )

        jornadas.update(liquidacion=liquidacion)

        if abono_aplicado > Decimal("0.00"):
          
            estado_abono = EstadoAdelanto.objects.filter(
                Q(codigo__iexact="abono") |
                Q(codigo__iexact="abonado")
            ).first()

            if not estado_abono:
                raise ValidationError(
                    "No existe un estado de adelanto con código 'abono' o 'abonado'."
                )

            Adelanto.objects.create(
                sucursal=sucursal,
                conductor=conductor,
                estado=estado_abono,
                monto=abono_aplicado,
                observacion=f"Abono aplicado en liquidación #{liquidacion.id}"
            )

    @action(detail=True, methods=["get"], url_path="recibo")
    def recibo(self, request, pk=None):
        liquidacion = self.get_object()

        jornadas = liquidacion.jornadas.select_related(
            "vehiculo",
            "estado"
        ).all().order_by("fecha", "id")

        saldo_actual = calcular_saldo_adelantos(
            liquidacion.conductor,
            liquidacion.sucursal
        )

        return Response({
            "id": liquidacion.id,
            "fecha_inicio": liquidacion.fecha_inicio,
            "fecha_fin": liquidacion.fecha_fin,
            "total_jornadas": liquidacion.total_jornadas,
            "total_adelantos_pendientes": liquidacion.total_adelantos_pendientes,
            "abono_aplicado": liquidacion.abono_aplicado,
            "ajuste_manual": liquidacion.ajuste_manual,
            "total_pago": liquidacion.total_pago,
            "notas": liquidacion.notas or "",
            "fecha_creacion": liquidacion.fecha_creacion,
            "saldo_actual_adelantos": saldo_actual["saldo_pendiente"],
            "sucursal": {
                "id": liquidacion.sucursal.id,
                "nombre": liquidacion.sucursal.nombre,
            } if liquidacion.sucursal else None,
            "conductor": {
                "id": liquidacion.conductor.id,
                "nombre": f"{liquidacion.conductor.nombre} {liquidacion.conductor.apellido}".strip(),
                "cedula": liquidacion.conductor.cedula,
            } if liquidacion.conductor else None,
            "jornadas": [
                {
                    "id": jornada.id,
                    "fecha": jornada.fecha,
                    "vehiculo": jornada.vehiculo.placa if jornada.vehiculo else "",
                    "kilometros_recorridos": jornada.kilometros_recorridos,
                    "ingreso_bruto": jornada.ingreso_bruto,
                    "pago_conductor": jornada.pago_conductor,
                    "estado": jornada.estado.nombre if jornada.estado else "",
                }
                for jornada in jornadas
            ],
        })

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

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(
                sucursal=user.sucursal,
                vehiculo__asignaciones__conductor__usuario=user,
                vehiculo__asignaciones__activa=True
            ).distinct()

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        vehiculo = serializer.validated_data.get("vehiculo")

        if not vehiculo:
            raise ValidationError("Debes indicar el vehículo.")

        if es_admin_sucursal(user) and vehiculo.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes registrar mantenimiento en otra sucursal.")

        mantenimiento = serializer.save(sucursal=vehiculo.sucursal)
        aplicar_mantenimiento_en_vehiculo(mantenimiento)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_admin_sucursal(user) and instance.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes modificar mantenimiento de otra sucursal.")

        mantenimiento = serializer.save()
        aplicar_mantenimiento_en_vehiculo(mantenimiento)


class ConfiguracionSistemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")

            if sucursal_id:
                config, _ = ConfiguracionSistema.objects.get_or_create(sucursal_id=sucursal_id)
                return Response(ConfiguracionSistemaSerializer(config).data)

            configs = ConfiguracionSistema.objects.select_related("sucursal").all()
            return Response(ConfiguracionSistemaSerializer(configs, many=True).data)

        if not user.sucursal:
            return Response(
                {"detail": "Tu usuario no tiene sucursal asignada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        config = obtener_configuracion_sucursal(user.sucursal)
        return Response(ConfiguracionSistemaSerializer(config).data)

    def patch(self, request):
        user = request.user

        if not es_superadmin(user) and not es_admin_sucursal(user):
            raise PermissionDenied("No tienes permiso para modificar la configuración.")

        if es_superadmin(user):
            sucursal_id = request.data.get("sucursal") or request.query_params.get("sucursal")

            if not sucursal_id:
                raise ValidationError("Debes indicar la sucursal que quieres configurar.")

            config, _ = ConfiguracionSistema.objects.get_or_create(sucursal_id=sucursal_id)
        else:
            config = obtener_configuracion_sucursal(user.sucursal)

        serializer = ConfiguracionSistemaSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(sucursal=config.sucursal)

        return Response(serializer.data)


class DashboardResumenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        hoy = timezone.localdate()
        inicio_semana, _ = obtener_rango_periodo("semana")
        inicio_mes, _ = obtener_rango_periodo("mes")

        jornadas = JornadaDiaria.objects.all()
        vehiculos = Vehiculo.objects.all()

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")
            if sucursal_id:
                jornadas = jornadas.filter(sucursal_id=sucursal_id)
                vehiculos = vehiculos.filter(sucursal_id=sucursal_id)

        elif es_admin_sucursal(user):
            jornadas = jornadas.filter(sucursal=user.sucursal)
            vehiculos = vehiculos.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            jornadas = jornadas.filter(sucursal=user.sucursal, conductor__usuario=user)
            vehiculos = vehiculos.filter(
                sucursal=user.sucursal,
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        jornadas_hoy = jornadas.filter(fecha=hoy)
        jornadas_semana = jornadas.filter(fecha__gte=inicio_semana, fecha__lte=hoy)
        jornadas_mes = jornadas.filter(fecha__gte=inicio_mes, fecha__lte=hoy)

        alertas = []
        for vehiculo in vehiculos:
            alertas.extend(obtener_alertas_vehiculo(vehiculo))

        data = {
            "fecha": str(hoy),
            "ingreso_dia": sumar_decimal(jornadas_hoy, "ingreso_bruto"),
            "ingreso_semana": sumar_decimal(jornadas_semana, "ingreso_bruto"),
            "ingreso_mes": sumar_decimal(jornadas_mes, "ingreso_bruto"),
            "ganancia_dueno_dia": sumar_decimal(jornadas_hoy, "ganancia_dueno"),
            "ganancia_dueno_semana": sumar_decimal(jornadas_semana, "ganancia_dueno"),
            "ganancia_dueno_mes": sumar_decimal(jornadas_mes, "ganancia_dueno"),
            "pago_taxistas_dia": sumar_decimal(jornadas_hoy, "pago_conductor"),
            "gastos_dia": sumar_decimal(jornadas_hoy, "total_gastos"),
            "km_dia": sumar_entero(jornadas_hoy, "kilometros_recorridos"),
            "km_semana": sumar_entero(jornadas_semana, "kilometros_recorridos"),
            "km_mes": sumar_entero(jornadas_mes, "kilometros_recorridos"),
            "vehiculos": vehiculos.count(),
            "alertas_mantenimiento": len(alertas),
            "alertas": alertas,
        }

        return Response(data)


class ReporteFinancieroView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        periodo = request.query_params.get("periodo", "dia")
        fecha_inicio, fecha_fin = obtener_rango_periodo(periodo)

        jornadas = JornadaDiaria.objects.all()

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

        jornadas = jornadas.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)

        data = {
            "periodo": periodo,
            "fecha_inicio": str(fecha_inicio),
            "fecha_fin": str(fecha_fin),
            "total_ingresos": sumar_decimal(jornadas, "ingreso_bruto"),
            "total_pago_conductores": sumar_decimal(jornadas, "pago_conductor"),
            "total_adelantos": sumar_decimal(jornadas, "total_adelantos"),
            "total_gastos": sumar_decimal(jornadas, "total_gastos"),
            "total_ganancia_dueno": sumar_decimal(jornadas, "ganancia_dueno"),
            "total_jornadas": jornadas.count(),
        }

        return Response(data)


class ReporteKilometrajeView(APIView):
    permission_classes = [IsAuthenticated]

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
        vehiculos = Vehiculo.objects.select_related("sucursal", "estado").all()

        if es_superadmin(user):
            sucursal_id = request.query_params.get("sucursal")
            if sucursal_id:
                vehiculos = vehiculos.filter(sucursal_id=sucursal_id)

        elif es_admin_sucursal(user):
            vehiculos = vehiculos.filter(sucursal=user.sucursal)

        elif es_taxista(user):
            vehiculos = vehiculos.filter(
                sucursal=user.sucursal,
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()

        else:
            return Response({"detail": "No tienes permisos."}, status=403)

        alertas = []

        for vehiculo in vehiculos:
            alertas.extend(obtener_alertas_vehiculo(vehiculo))

        return Response(alertas)