from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Q, Sum
from django.utils import timezone

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
    sumar_decimal,
    sumar_entero,
)


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
    permission_classes = [EsAdminSucursalOSuperAdmin]


class EstadoJornadaViewSet(viewsets.ModelViewSet):
    queryset = EstadoJornada.objects.all().order_by("nombre")
    serializer_class = EstadoJornadaSerializer
    permission_classes = [EsAdminSucursalOSuperAdmin]


class TipoGastoViewSet(viewsets.ModelViewSet):
    queryset = TipoGasto.objects.all().order_by("nombre")
    serializer_class = TipoGastoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsAdminSucursalOSuperAdmin()]

class EstadoGastoViewSet(viewsets.ModelViewSet):
    queryset = EstadoGasto.objects.all().order_by("nombre")
    serializer_class = EstadoGastoSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]

        return [EsAdminSucursalOSuperAdmin()]


class EstadoAdelantoViewSet(viewsets.ModelViewSet):
    queryset = EstadoAdelanto.objects.all().order_by("nombre")
    serializer_class = EstadoAdelantoSerializer
    permission_classes = [EsAdminSucursalOSuperAdmin]


class TipoMantenimientoViewSet(viewsets.ModelViewSet):
    queryset = TipoMantenimiento.objects.all().order_by("nombre")
    serializer_class = TipoMantenimientoSerializer
    permission_classes = [EsAdminSucursalOSuperAdmin]


class EstadoMantenimientoViewSet(viewsets.ModelViewSet):
    queryset = EstadoMantenimiento.objects.all().order_by("nombre")
    serializer_class = EstadoMantenimientoSerializer
    permission_classes = [EsAdminSucursalOSuperAdmin]


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
            return queryset.filter(
                Q(sucursal__isnull=True) |
                Q(rol__codigo="admin_sucursal")
            )

        if es_admin_sucursal(user):
            return queryset.filter(
                sucursal=user.sucursal
            ).exclude(
                rol__codigo__in=["superadmin", "usuario_sistema", "admin_sucursal"]
            )

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
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if not rol or rol.codigo != "taxista":
                raise PermissionDenied("Un administrador de sucursal solo puede crear usuarios taxistas.")

            serializer.save()
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

            serializer.save()
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
            return qs.filter(sucursal__isnull=True)

        if es_admin_sucursal(user):
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
            if instance.sucursal_id is not None:
                raise PermissionDenied("No puedes modificar conductores de una sucursal desde el panel superadmin.")

            if actualizar_porcentaje and porcentaje is None:
                porcentaje = obtener_configuracion_sucursal(None).porcentaje_pago_conductor

            if actualizar_porcentaje:
                serializer.save(sucursal=None, porcentaje_pago=porcentaje)
            else:
                serializer.save(sucursal=None)
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

        if es_superadmin(user):
            qs = qs.filter(sucursal__isnull=True)

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
            return qs.filter(sucursal__isnull=True)

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

        if es_superadmin(user):
            return qs.filter(sucursal__isnull=True)

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
            if conductor.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes asignar conductores de una sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes asignar vehículos de una sucursal desde el panel superadmin."
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
                    "No puedes modificar asignaciones de una sucursal desde el panel superadmin."
                )

            if conductor.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes asignar conductores de una sucursal desde el panel superadmin."
                )

            if vehiculo.sucursal_id is not None:
                raise PermissionDenied(
                    "No puedes asignar vehículos de una sucursal desde el panel superadmin."
                )

            serializer.save(sucursal=None)
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
        # Flujo principal: el % lo define el conductor. Si el conductor no tiene
        # un % propio (None o 0), se cae al % por defecto de la sucursal.
        porcentaje = getattr(conductor, "porcentaje_pago", None)

        if porcentaje is None or Decimal(porcentaje) == Decimal("0.00"):
            return self._obtener_porcentaje_fallback(sucursal)

        return porcentaje

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

        kilometraje_final = request.data.get("kilometraje_final")
        ingreso_bruto = request.data.get("ingreso_bruto", jornada.ingreso_bruto)

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
            porcentaje
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
    
    @action(detail=True, methods=["patch"], url_path="registrar-ingreso")
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

        ingreso_bruto = Decimal(str(request.data.get("ingreso_bruto", "0.00") or "0.00"))
        monto_alquiler = Decimal(str(request.data.get("monto_alquiler", "0.00") or "0.00"))

        # Prioridad del %: body explicito > conductor.porcentaje_pago > config de sucursal.
        porcentaje_body = request.data.get("porcentaje_pago_conductor")

        if porcentaje_body not in (None, ""):
            porcentaje = Decimal(str(porcentaje_body))
        else:
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

    def perform_create(self, serializer):
        user = self.request.user
        jornada = serializer.validated_data.get("jornada")

        if not jornada:
            raise ValidationError("El adelanto debe estar asociado a una jornada.")

        if es_admin_sucursal(user) and jornada.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes registrar adelantos en otra sucursal.")

        adelanto = serializer.save(
            sucursal=jornada.sucursal,
            conductor=jornada.conductor
        )

        recalcular_totales_jornada(adelanto.jornada)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_admin_sucursal(user) and instance.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes modificar adelantos de otra sucursal.")

        adelanto = serializer.save()

        recalcular_totales_jornada(adelanto.jornada)

    def perform_destroy(self, instance):
        jornada = instance.jornada
        instance.delete()
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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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

class DashboardFinancieroView(APIView):
    permission_classes = [IsAuthenticated]

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