from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Sum
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

        if user.rol.codigo != "superadmin" and not user.sucursal:
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
    queryset = Rol.objects.all().order_by("nombre")
    serializer_class = RolSerializer
    permission_classes = [EsSuperAdmin]


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
        qs = Usuario.objects.select_related("rol", "sucursal").all().order_by("-id")

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal).exclude(rol__codigo="superadmin")

        return qs.none()

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(self.get_serializer(request.user).data)

    def perform_create(self, serializer):
        user = self.request.user
        rol = serializer.validated_data.get("rol")
        sucursal = serializer.validated_data.get("sucursal")

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if not user.sucursal:
                raise ValidationError("Tu usuario no tiene una sucursal asignada.")

            if rol and rol.codigo == "superadmin":
                raise PermissionDenied("No puedes crear usuarios superadmin.")

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

            if rol and rol.codigo == "superadmin":
                raise PermissionDenied("No puedes asignar rol superadmin.")

            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar usuarios.")


class ConductorViewSet(viewsets.ModelViewSet):
    serializer_class = ConductorSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Conductor.objects.select_related("sucursal", "usuario").all()

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
            serializer.save()
            return

        if es_admin_sucursal(user):
            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear conductores.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar conductores de otra sucursal.")
            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar conductores.")


class VehiculoViewSet(viewsets.ModelViewSet):
    serializer_class = VehiculoSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Vehiculo.objects.select_related("sucursal", "estado").all()

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        if es_taxista(user):
            return qs.filter(
                sucursal=user.sucursal,
                asignaciones__conductor__usuario=user,
                asignaciones__activa=True
            ).distinct()

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear vehículos.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_superadmin(user):
            serializer.save()
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

    def get_queryset(self):
        user = self.request.user
        qs = AsignacionVehiculo.objects.select_related(
            "sucursal",
            "conductor",
            "vehiculo"
        ).all()

        if es_superadmin(user):
            return qs

        if es_admin_sucursal(user):
            return qs.filter(sucursal=user.sucursal)

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        conductor = serializer.validated_data.get("conductor")
        vehiculo = serializer.validated_data.get("vehiculo")

        if conductor.sucursal_id != vehiculo.sucursal_id:
            raise ValidationError("El conductor y el vehículo deben pertenecer a la misma sucursal.")

        if es_superadmin(user):
            serializer.save(sucursal=conductor.sucursal)
            return

        if es_admin_sucursal(user):
            if conductor.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes asignar conductores de otra sucursal.")
            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para crear asignaciones.")

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if es_superadmin(user):
            serializer.save()
            return

        if es_admin_sucursal(user):
            if instance.sucursal_id != user.sucursal_id:
                raise PermissionDenied("No puedes modificar asignaciones de otra sucursal.")
            serializer.save(sucursal=user.sucursal)
            return

        raise PermissionDenied("No tienes permiso para modificar asignaciones.")


class JornadaDiariaViewSet(viewsets.ModelViewSet):
    serializer_class = JornadaDiariaSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [EsAdminSucursalOSuperAdmin()]
        return [IsAuthenticated()]

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

        if conductor_id:
            qs = qs.filter(conductor_id=conductor_id)

        if vehiculo_id:
            qs = qs.filter(vehiculo_id=vehiculo_id)

        return qs

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

        if conductor.sucursal_id != vehiculo.sucursal_id:
            raise ValidationError("El conductor y el vehículo deben pertenecer a la misma sucursal.")

        if es_admin_sucursal(user) and conductor.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes registrar jornadas en otra sucursal.")

        if es_taxista(user) and conductor.usuario_id != user.id:
            raise PermissionDenied("No puedes crear jornadas para otro conductor.")

        asignacion_activa = AsignacionVehiculo.objects.filter(
            sucursal=conductor.sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            activa=True
        ).exists()

        if not asignacion_activa:
            raise ValidationError("El conductor no tiene una asignación activa con ese vehículo.")

        porcentaje = conductor.porcentaje_pago

        campos_calculados = calcular_campos_jornada(
            serializer.validated_data.get("kilometraje_inicial"),
            serializer.validated_data.get("kilometraje_final"),
            serializer.validated_data.get("ingreso_bruto"),
            porcentaje
        )

        jornada = serializer.save(
            sucursal=conductor.sucursal,
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

        if es_admin_sucursal(user) and instance.sucursal_id != user.sucursal_id:
            raise PermissionDenied("No puedes modificar jornadas de otra sucursal.")

        if es_taxista(user) and instance.conductor.usuario_id != user.id:
            raise PermissionDenied("No puedes modificar jornadas de otro conductor.")

        conductor = serializer.validated_data.get("conductor", instance.conductor)
        vehiculo = serializer.validated_data.get("vehiculo", instance.vehiculo)

        if conductor.sucursal_id != vehiculo.sucursal_id:
            raise ValidationError("El conductor y el vehículo deben pertenecer a la misma sucursal.")

        porcentaje = conductor.porcentaje_pago

        km_inicial = serializer.validated_data.get("kilometraje_inicial", instance.kilometraje_inicial)
        km_final = serializer.validated_data.get("kilometraje_final", instance.kilometraje_final)
        ingreso_bruto = serializer.validated_data.get("ingreso_bruto", instance.ingreso_bruto)

        campos_calculados = calcular_campos_jornada(
            km_inicial,
            km_final,
            ingreso_bruto,
            porcentaje
        )

        jornada = serializer.save(
            sucursal=conductor.sucursal,
            conductor=conductor,
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