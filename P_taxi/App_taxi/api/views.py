from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Q, Sum
from django.http import HttpResponse
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
            return queryset.exclude(codigo="superadmin")

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
    permission_classes = [EsAdminSucursalOSuperAdmin]


class EstadoGastoViewSet(viewsets.ModelViewSet):
    queryset = EstadoGasto.objects.all().order_by("nombre")
    serializer_class = EstadoGastoSerializer
    permission_classes = [EsAdminSucursalOSuperAdmin]


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
            if instance.sucursal_id is not None:
                raise PermissionDenied("No puedes modificar conductores de una sucursal desde el panel superadmin.")

            serializer.save(sucursal=None)
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

        campos_calculados = calcular_campos_jornada(
            serializer.validated_data.get("kilometraje_inicial"),
            serializer.validated_data.get("kilometraje_final"),
            serializer.validated_data.get("ingreso_bruto"),
            porcentaje
        )

        jornada = serializer.save(
            sucursal=sucursal,
            conductor=conductor,
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
        sucursal = serializer.validated_data.get("sucursal")

        if es_admin_sucursal(user):
            if sucursal and sucursal.id != user.sucursal_id:
                raise PermissionDenied("No puedes registrar adelantos en otra sucursal.")

            serializer.save(sucursal=user.sucursal)
            return

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_admin_sucursal(user) and instance.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes modificar adelantos de otra sucursal.")

        serializer.save()

    @action(detail=True, methods=['get'], url_path='recibo')
    def recibo(self, request, pk=None):
        adelanto = self.get_object()

        conductor = f"{adelanto.conductor.nombre} {adelanto.conductor.apellido}".strip()
        sucursal = adelanto.sucursal.nombre if adelanto.sucursal else "Sin sucursal"
        tipo = adelanto.get_tipo_display()
        monto = f"C$ {adelanto.monto:,.2f}"
        fecha = adelanto.fecha.strftime("%d/%m/%Y") if adelanto.fecha else ""
        observacion = adelanto.observacion or "Sin observación"
        es_abono = adelanto.tipo == Adelanto.TIPO_ABONO
        color = "#16a34a" if es_abono else "#dc2626"

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Recibo #{adelanto.id} - {tipo}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; background: #f1f5f9; margin: 0; padding: 24px; color: #0f172a; }}
  .recibo {{ max-width: 480px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 28px 32px; }}
  .cabecera {{ text-align: center; border-bottom: 2px dashed #cbd5e1; padding-bottom: 16px; margin-bottom: 18px; }}
  .cabecera h1 {{ margin: 0; font-size: 20px; }}
  .cabecera p {{ margin: 4px 0 0; color: #64748b; font-size: 13px; }}
  .tipo {{ display: inline-block; margin-top: 10px; padding: 4px 14px; border-radius: 999px; color: #fff; font-weight: bold; font-size: 13px; background: {color}; }}
  .fila {{ display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
  .fila .etq {{ color: #64748b; font-weight: bold; }}
  .fila .val {{ text-align: right; font-weight: bold; }}
  .monto {{ text-align: center; margin: 20px 0 6px; font-size: 30px; font-weight: 900; color: {color}; }}
  .obs {{ margin-top: 14px; background: #f8fafc; border-radius: 10px; padding: 12px 14px; font-size: 13px; color: #334155; }}
  .acciones {{ text-align: center; margin-top: 22px; }}
  .btn {{ background: #F5B800; color: #fff; border: none; border-radius: 10px; padding: 12px 26px; font-size: 14px; font-weight: bold; cursor: pointer; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .recibo {{ border: none; }} .acciones {{ display: none; }} }}
</style>
</head>
<body>
  <div class="recibo">
    <div class="cabecera">
      <h1>Recibo de {tipo}</h1>
      <p>Recibo N&deg; {adelanto.id}</p>
      <span class="tipo">{tipo}</span>
    </div>

    <div class="monto">{monto}</div>

    <div class="fila"><span class="etq">Conductor</span><span class="val">{conductor}</span></div>
    <div class="fila"><span class="etq">Sucursal</span><span class="val">{sucursal}</span></div>
    <div class="fila"><span class="etq">Tipo</span><span class="val">{tipo}</span></div>
    <div class="fila"><span class="etq">Monto</span><span class="val">{monto}</span></div>
    <div class="fila"><span class="etq">Fecha</span><span class="val">{fecha}</span></div>

    <div class="obs"><strong>Observaci&oacute;n:</strong> {observacion}</div>

    <div class="acciones">
      <button class="btn" onclick="window.print()">&#128424; Imprimir recibo</button>
    </div>
  </div>
</body>
</html>"""

        return HttpResponse(html, content_type="text/html")


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
        ).all()

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(conductor__usuario=user)

        return qs.none()

    def perform_create(self, serializer):
        liq = serializer.save()

        # Bloquear todas las jornadas del rango asignándoles esta liquidación
        JornadaDiaria.objects.filter(
            conductor=liq.conductor,
            fecha__gte=liq.fecha_inicio,
            fecha__lte=liq.fecha_fin,
            liquidacion__isnull=True
        ).update(liquidacion=liq)

    @action(detail=False, methods=['get'], url_path='preview')
    def preview(self, request):
        conductor_id = request.query_params.get('conductor_id')
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        if not (conductor_id and fecha_inicio and fecha_fin):
            return Response(
                {"detail": "conductor_id, fecha_inicio y fecha_fin son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Jornadas del conductor en el rango que aún NO están liquidadas
        jornadas = JornadaDiaria.objects.filter(
            conductor_id=conductor_id,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            liquidacion__isnull=True
        ).order_by('fecha')

        total_jornadas = sum(
            (j.pago_conductor for j in jornadas),
            Decimal("0.00")
        )

        # Adelantos pendientes del conductor (adelantos - abonos)
        adelantos = Adelanto.objects.filter(conductor_id=conductor_id, tipo='ADELANTO')
        abonos = Adelanto.objects.filter(conductor_id=conductor_id, tipo='ABONO')
        total_adelantos = sum((a.monto for a in adelantos), Decimal("0.00"))
        total_abonos = sum((a.monto for a in abonos), Decimal("0.00"))
        pendiente_adelantos = max(total_adelantos - total_abonos, Decimal("0.00"))

        return Response({
            'jornadas': [
                {'id': j.id, 'fecha': j.fecha, 'monto': j.pago_conductor}
                for j in jornadas
            ],
            'total_jornadas': total_jornadas,
            'pendiente_adelantos': pendiente_adelantos,
            'total_sugerido': total_jornadas - pendiente_adelantos,
            'jornadas_count': jornadas.count()
        })

    @action(detail=True, methods=['get'], url_path='recibo')
    def recibo(self, request, pk=None):
        liq = self.get_object()
        jornadas = liq.jornadas.all().order_by('fecha')
        filas = ''.join([
            f"<tr><td>{j.fecha}</td><td>C$ {j.pago_conductor}</td></tr>"
            for j in jornadas
        ])
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Liquidación</title>
    <style>body{{font-family:Arial;max-width:500px;margin:40px auto;padding:20px}}
    table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:6px}}
    .total{{font-size:1.2em;font-weight:bold}}@media print{{button{{display:none}}}}</style></head>
    <body><h2>Recibo de Liquidación — TaxiAdmin</h2>
    <p><b>Conductor:</b> {liq.conductor.nombre} {liq.conductor.apellido}</p>
    <p><b>Período:</b> {liq.fecha_inicio} al {liq.fecha_fin}</p>
    <table><tr><th>Fecha</th><th>Ganancia conductor</th></tr>{filas}</table>
    <br>
    <p>Total jornadas: C$ {liq.total_jornadas}</p>
    <p>Adelantos pendientes: - C$ {liq.total_adelantos_pendientes}</p>
    <p>Ajuste manual: C$ {liq.ajuste_manual}</p>
    <p class="total">TOTAL A PAGAR: C$ {liq.total_pago}</p>
    <p>Notas: {liq.notas or '—'}</p>
    <br><button onclick="window.print()">🖨 Imprimir</button>
    </body></html>"""
        return HttpResponse(html)


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