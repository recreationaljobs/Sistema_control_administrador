from rest_framework import serializers
from decimal import Decimal
from django.db.models import Sum

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


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = "__all__"


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ["id", "nombre", "codigo"]


class EstadoVehiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoVehiculo
        fields = ["id", "nombre", "codigo"]


class EstadoJornadaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoJornada
        fields = ["id", "nombre", "codigo"]


class TipoGastoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoGasto
        fields = ["id", "nombre", "codigo"]


class EstadoGastoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoGasto
        fields = ["id", "nombre", "codigo"]


class EstadoAdelantoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoAdelanto
        fields = ["id", "nombre", "codigo"]


class TipoMantenimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoMantenimiento
        fields = ["id", "nombre", "codigo"]


class EstadoMantenimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoMantenimiento
        fields = ["id", "nombre", "codigo"]


from rest_framework import serializers
from App_taxi.models import Usuario, Rol, Sucursal, Conductor


class UsuarioSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True)
    rol_codigo = serializers.CharField(source="rol.codigo", read_only=True)
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

    conductor_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True
    )

    conductor_nombre = serializers.SerializerMethodField()

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "rol",
            "rol_nombre",
            "rol_codigo",
            "sucursal",
            "sucursal_nombre",
            "is_active",
            "is_staff",
            "is_superuser",
            "conductor_id",
            "conductor_nombre",
        ]

        read_only_fields = [
            "is_staff",
            "is_superuser",
            "rol_nombre",
            "rol_codigo",
            "sucursal_nombre",
            "conductor_nombre",
        ]

        extra_kwargs = {
            "sucursal": {
                "required": False,
                "allow_null": True,
            },
            "rol": {
                "required": True,
                "allow_null": False,
            },
        }

    def get_conductor_nombre(self, obj):
        conductor = getattr(obj, "perfil_conductor", None)

        if not conductor:
            return None

        return f"{conductor.nombre} {conductor.apellido}".strip()

    def validate(self, attrs):
        request = self.context.get("request")
        usuario_actual = request.user if request else None

        rol = attrs.get("rol") or getattr(self.instance, "rol", None)
        sucursal = attrs.get("sucursal") or getattr(self.instance, "sucursal", None)
        conductor_id = attrs.get("conductor_id", None)

        if not rol:
            raise serializers.ValidationError({
                "rol": "Debes seleccionar un rol para este usuario."
            })

        codigo_rol = rol.codigo

        codigo_usuario_actual = (
            usuario_actual.rol.codigo
            if usuario_actual and usuario_actual.rol
            else None
        )

        if codigo_usuario_actual == "admin_sucursal":
            if codigo_rol != "taxista":
                raise serializers.ValidationError({
                    "rol": "Un administrador de sucursal solo puede crear usuarios taxistas."
                })

        if codigo_rol == "admin_sucursal":
            if not sucursal:
                raise serializers.ValidationError({
                    "sucursal": "Debes seleccionar una sucursal para este administrador."
                })

        if codigo_rol == "taxista":
            if not self.instance and not conductor_id:
                raise serializers.ValidationError({
                    "conductor_id": "Debes seleccionar el taxista/conductor al que se le creará el usuario."
                })

            if conductor_id:
                try:
                    conductor = Conductor.objects.select_related(
                        "sucursal",
                        "usuario"
                    ).get(id=conductor_id)
                except Conductor.DoesNotExist:
                    raise serializers.ValidationError({
                        "conductor_id": "El taxista/conductor seleccionado no existe."
                    })

                if conductor.usuario and conductor.usuario != self.instance:
                    raise serializers.ValidationError({
                        "conductor_id": "Este taxista/conductor ya tiene un usuario asociado."
                    })

                if codigo_usuario_actual == "superadmin":
                    if conductor.sucursal_id is not None:
                        raise serializers.ValidationError({
                            "conductor_id": "Desde el panel superadmin solo puedes crear usuarios para conductores del superadmin."
                        })

                if codigo_usuario_actual == "admin_sucursal":
                    if not usuario_actual.sucursal:
                        raise serializers.ValidationError({
                            "sucursal": "Tu usuario no tiene una sucursal asignada."
                        })

                    if conductor.sucursal_id != usuario_actual.sucursal_id:
                        raise serializers.ValidationError({
                            "conductor_id": "No puedes crear usuario para un taxista de otra sucursal."
                        })

                attrs["sucursal"] = conductor.sucursal

        if codigo_rol in ["superadmin", "usuario_sistema"]:
            attrs["sucursal"] = None

        return attrs

    def create(self, validated_data):
        conductor_id = validated_data.pop("conductor_id", None)
        password = validated_data.pop("password", None)

        user = Usuario(**validated_data)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save()

        if conductor_id:
            conductor = Conductor.objects.get(id=conductor_id)
            conductor.usuario = user
            conductor.save()

        return user

    def update(self, instance, validated_data):
        conductor_id = validated_data.pop("conductor_id", None)
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        if conductor_id:
            Conductor.objects.filter(usuario=instance).update(usuario=None)

            conductor = Conductor.objects.get(id=conductor_id)
            conductor.usuario = instance
            conductor.save()

        return instance

class ConductorSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(
        source="sucursal.nombre",
        read_only=True
    )

    usuario_username = serializers.CharField(
        source="usuario.username",
        read_only=True
    )

    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Conductor
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "usuario",
            "usuario_username",
            "nombre",
            "apellido",
            "nombre_completo",
            "telefono",
            "cedula",
            "direccion",
            "licencia",
            "vencimiento_licencia",
            "numero_licencia",
            "fecha_inicio_licencia",
            "fecha_vencimiento_licencia",
            "fecha_registro",
            "activo",
        ]
        read_only_fields = [
            "fecha_registro",
            "sucursal_nombre",
            "usuario_username",
            "nombre_completo",
        ]
        extra_kwargs = {
            "sucursal": {
                "required": False,
                "allow_null": True,
            },
            "usuario": {
                "required": False,
                "allow_null": True,
            },
        }

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}".strip()

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        if not user:
            return attrs

        cedula = attrs.get("cedula", getattr(self.instance, "cedula", None))

        if user.rol and user.rol.codigo == "superadmin":
            attrs["sucursal"] = None

            if cedula:
                qs = Conductor.objects.filter(
                    sucursal__isnull=True,
                    cedula=cedula
                )

                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)

                if qs.exists():
                    raise serializers.ValidationError({
                        "cedula": "Ya existe un conductor del superadmin con esta cédula."
                    })

            return attrs

        if user.rol and user.rol.codigo == "admin_sucursal":
            if not user.sucursal:
                raise serializers.ValidationError({
                    "sucursal": "Tu usuario no tiene una sucursal asignada."
                })

            attrs["sucursal"] = user.sucursal

            if cedula:
                qs = Conductor.objects.filter(
                    sucursal=user.sucursal,
                    cedula=cedula
                )

                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)

                if qs.exists():
                    raise serializers.ValidationError({
                        "cedula": "Ya existe un conductor con esta cédula en tu sucursal."
                    })

            return attrs

        return attrs

class VehiculoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    estado_codigo = serializers.CharField(source="estado.codigo", read_only=True)

    proximo_cambio_aceite = serializers.SerializerMethodField()
    proximo_mantenimiento = serializers.SerializerMethodField()
    faltan_km_cambio_aceite = serializers.SerializerMethodField()
    faltan_km_mantenimiento = serializers.SerializerMethodField()
    necesita_cambio_aceite = serializers.SerializerMethodField()
    necesita_mantenimiento = serializers.SerializerMethodField()
    alerta_cambio_aceite = serializers.SerializerMethodField()
    alerta_mantenimiento = serializers.SerializerMethodField()

    class Meta:
        model = Vehiculo
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "numero",
            "placa",
            "marca",
            "modelo",
            "anio",
            "color",
            "numero_motor",
            "numero_chasis",
            "tipo_combustible",
            "kilometraje_actual",
            "km_ultimo_cambio_aceite",
            "km_intervalo_cambio_aceite",
            "km_ultimo_mantenimiento",
            "km_intervalo_mantenimiento",
            "alerta_previa_km",
            "fecha_registro",
            "proximo_cambio_aceite",
            "proximo_mantenimiento",
            "faltan_km_cambio_aceite",
            "faltan_km_mantenimiento",
            "necesita_cambio_aceite",
            "necesita_mantenimiento",
            "alerta_cambio_aceite",
            "alerta_mantenimiento",
        ]

        read_only_fields = [
            "id",
            "sucursal_nombre",
            "estado_nombre",
            "estado_codigo",
            "fecha_registro",
            "proximo_cambio_aceite",
            "proximo_mantenimiento",
            "faltan_km_cambio_aceite",
            "faltan_km_mantenimiento",
            "necesita_cambio_aceite",
            "necesita_mantenimiento",
            "alerta_cambio_aceite",
            "alerta_mantenimiento",
        ]

        extra_kwargs = {
            "sucursal": {
                "required": False,
                "allow_null": True,
            },
            "estado": {
                "required": False,
                "allow_null": True,
            },
        }

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        if not user:
            return attrs

        numero = attrs.get("numero", getattr(self.instance, "numero", None))
        placa = attrs.get("placa", getattr(self.instance, "placa", None))

        if user.rol and user.rol.codigo == "superadmin":
            attrs["sucursal"] = None

            if numero:
                qs = Vehiculo.objects.filter(
                    sucursal__isnull=True,
                    numero=numero
                )

                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)

                if qs.exists():
                    raise serializers.ValidationError({
                        "numero": "Ya existe un vehículo del superadmin con este número."
                    })

            if placa:
                qs_placa = Vehiculo.objects.filter(placa=placa)

                if self.instance:
                    qs_placa = qs_placa.exclude(pk=self.instance.pk)

                if qs_placa.exists():
                    raise serializers.ValidationError({
                        "placa": "Ya existe un vehículo registrado con esta placa."
                    })

            return attrs

        if user.rol and user.rol.codigo == "admin_sucursal":
            if not user.sucursal:
                raise serializers.ValidationError({
                    "sucursal": "Tu usuario no tiene una sucursal asignada."
                })

            attrs["sucursal"] = user.sucursal

            if numero:
                qs = Vehiculo.objects.filter(
                    sucursal=user.sucursal,
                    numero=numero
                )

                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)

                if qs.exists():
                    raise serializers.ValidationError({
                        "numero": "Ya existe un vehículo con este número en tu sucursal."
                    })

            if placa:
                qs_placa = Vehiculo.objects.filter(placa=placa)

                if self.instance:
                    qs_placa = qs_placa.exclude(pk=self.instance.pk)

                if qs_placa.exists():
                    raise serializers.ValidationError({
                        "placa": "Ya existe un vehículo registrado con esta placa."
                    })

            return attrs

        return attrs

    def get_proximo_cambio_aceite(self, obj):
        return obj.km_ultimo_cambio_aceite + obj.km_intervalo_cambio_aceite

    def get_proximo_mantenimiento(self, obj):
        return obj.km_ultimo_mantenimiento + obj.km_intervalo_mantenimiento

    def get_faltan_km_cambio_aceite(self, obj):
        return self.get_proximo_cambio_aceite(obj) - obj.kilometraje_actual

    def get_faltan_km_mantenimiento(self, obj):
        return self.get_proximo_mantenimiento(obj) - obj.kilometraje_actual

    def get_necesita_cambio_aceite(self, obj):
        return obj.kilometraje_actual >= self.get_proximo_cambio_aceite(obj)

    def get_necesita_mantenimiento(self, obj):
        return obj.kilometraje_actual >= self.get_proximo_mantenimiento(obj)

    def get_alerta_cambio_aceite(self, obj):
        faltan = self.get_faltan_km_cambio_aceite(obj)
        return 0 <= faltan <= obj.alerta_previa_km

    def get_alerta_mantenimiento(self, obj):
        faltan = self.get_faltan_km_mantenimiento(obj)
        return 0 <= faltan <= obj.alerta_previa_km


class AsignacionVehiculoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    conductor_nombre = serializers.SerializerMethodField()
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    vehiculo_numero = serializers.CharField(source="vehiculo.numero", read_only=True)
    vehiculo_descripcion = serializers.SerializerMethodField()

    class Meta:
        model = AsignacionVehiculo
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "conductor",
            "conductor_nombre",
            "vehiculo",
            "vehiculo_placa",
            "vehiculo_numero",
            "vehiculo_descripcion",
            "fecha_inicio",
            "fecha_fin",
            "activa",
        ]

        read_only_fields = [
            "id",
            "sucursal_nombre",
            "conductor_nombre",
            "vehiculo_placa",
            "vehiculo_numero",
            "vehiculo_descripcion",
        ]

        extra_kwargs = {
            "sucursal": {
                "required": False,
                "allow_null": True,
            },
        }

    def get_conductor_nombre(self, obj):
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def get_vehiculo_descripcion(self, obj):
        return f"{obj.vehiculo.numero} - {obj.vehiculo.placa} - {obj.vehiculo.marca} {obj.vehiculo.modelo}"

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        conductor = attrs.get("conductor", getattr(self.instance, "conductor", None))
        vehiculo = attrs.get("vehiculo", getattr(self.instance, "vehiculo", None))
        activa = attrs.get("activa", getattr(self.instance, "activa", True))

        if not conductor:
            raise serializers.ValidationError({
                "conductor": "Debes seleccionar un conductor."
            })

        if not vehiculo:
            raise serializers.ValidationError({
                "vehiculo": "Debes seleccionar un vehículo."
            })

        if not user or not user.rol:
            raise serializers.ValidationError(
                "No se pudo validar el usuario autenticado."
            )

        codigo_rol = user.rol.codigo

        if codigo_rol == "superadmin":
            if conductor.sucursal_id is not None:
                raise serializers.ValidationError({
                    "conductor": "Desde el panel superadmin solo puedes asignar conductores del superadmin."
                })

            if vehiculo.sucursal_id is not None:
                raise serializers.ValidationError({
                    "vehiculo": "Desde el panel superadmin solo puedes asignar vehículos del superadmin."
                })

            attrs["sucursal"] = None

        elif codigo_rol == "admin_sucursal":
            if not user.sucursal:
                raise serializers.ValidationError({
                    "sucursal": "Tu usuario no tiene una sucursal asignada."
                })

            if conductor.sucursal_id != user.sucursal_id:
                raise serializers.ValidationError({
                    "conductor": "No puedes asignar conductores de otra sucursal."
                })

            if vehiculo.sucursal_id != user.sucursal_id:
                raise serializers.ValidationError({
                    "vehiculo": "No puedes asignar vehículos de otra sucursal."
                })

            attrs["sucursal"] = user.sucursal

        else:
            raise serializers.ValidationError(
                "No tienes permiso para crear asignaciones."
            )

        if activa:
            qs_vehiculo = AsignacionVehiculo.objects.filter(
                vehiculo=vehiculo,
                activa=True
            )

            qs_conductor = AsignacionVehiculo.objects.filter(
                conductor=conductor,
                activa=True
            )

            if self.instance:
                qs_vehiculo = qs_vehiculo.exclude(pk=self.instance.pk)
                qs_conductor = qs_conductor.exclude(pk=self.instance.pk)

            if qs_vehiculo.exists():
                raise serializers.ValidationError({
                    "vehiculo": "Ese vehículo ya tiene una asignación activa."
                })

            if qs_conductor.exists():
                raise serializers.ValidationError({
                    "conductor": "Ese conductor ya tiene una asignación activa."
                })

        return attrs


class GastoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    conductor_nombre = serializers.SerializerMethodField()
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    tipo_gasto_nombre = serializers.CharField(source="tipo_gasto.nombre", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    estado_codigo = serializers.CharField(source="estado.codigo", read_only=True)

    class Meta:
        model = Gasto
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "jornada",
            "vehiculo",
            "vehiculo_placa",
            "conductor",
            "conductor_nombre",
            "tipo_gasto",
            "tipo_gasto_nombre",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "descripcion",
            "monto",
            "fecha",
        ]
        read_only_fields = [
            "id",
            "sucursal_nombre",
            "vehiculo_placa",
            "conductor_nombre",
            "tipo_gasto_nombre",
            "estado_nombre",
            "estado_codigo",
        ]

    def get_conductor_nombre(self, obj):
        if not obj.conductor:
            return None
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def validate(self, attrs):
        jornada = attrs.get("jornada", getattr(self.instance, "jornada", None))
        vehiculo = attrs.get("vehiculo", getattr(self.instance, "vehiculo", None))
        conductor = attrs.get("conductor", getattr(self.instance, "conductor", None))
        sucursal = attrs.get("sucursal", getattr(self.instance, "sucursal", None))

        if jornada:
            if vehiculo and vehiculo.id != jornada.vehiculo_id:
                raise serializers.ValidationError("El vehículo no coincide con la jornada.")

            if conductor and conductor.id != jornada.conductor_id:
                raise serializers.ValidationError("El conductor no coincide con la jornada.")

            if sucursal and sucursal.id != jornada.sucursal_id:
                raise serializers.ValidationError("La sucursal no coincide con la jornada.")

        return attrs


class AdelantoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    conductor_nombre = serializers.SerializerMethodField()
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    estado_codigo = serializers.CharField(source="estado.codigo", read_only=True)
    tipo = serializers.SerializerMethodField()
    tipo_display = serializers.SerializerMethodField()

    class Meta:
        model = Adelanto
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "conductor",
            "conductor_nombre",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "tipo",
            "tipo_display",
            "monto",
            "fecha",
            "observacion",
        ]

        read_only_fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "conductor_nombre",
            "estado_nombre",
            "estado_codigo",
            "tipo",
            "tipo_display",
            "fecha",
        ]

        extra_kwargs = {
            "estado": {
                "required": False,
                "allow_null": True,
            },
            "observacion": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
        }

    def get_conductor_nombre(self, obj):
        if not obj.conductor:
            return ""

        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def get_tipo(self, obj):
        if not obj.estado:
            return "ADELANTO"

        codigo = obj.estado.codigo.lower()

        if codigo in ["abono", "abonado"]:
            return "ABONO"

        return "ADELANTO"

    def get_tipo_display(self, obj):
        if not obj.estado:
            return "Movimiento"

        codigo = obj.estado.codigo.lower()

        if codigo in ["abono", "abonado"]:
            return "Abono"

        if codigo == "anticipo":
            return "Anticipo"

        return "Adelanto"

    def validate(self, attrs):
        monto = attrs.get("monto", getattr(self.instance, "monto", None))

        if monto is not None and monto <= Decimal("0.00"):
            raise serializers.ValidationError({
                "monto": "El monto debe ser mayor que cero."
            })

        return attrs
class JornadaDiariaSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.SerializerMethodField()
    conductor_nombre = serializers.SerializerMethodField()
    vehiculo_placa = serializers.SerializerMethodField()
    vehiculo_numero = serializers.SerializerMethodField()
    vehiculo_descripcion = serializers.SerializerMethodField()
    estado_nombre = serializers.SerializerMethodField()
    estado_codigo = serializers.SerializerMethodField()

    kilometraje_final = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    gastos = GastoSerializer(many=True, read_only=True)

    class Meta:
        model = JornadaDiaria
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "fecha",
            "conductor",
            "conductor_nombre",
            "vehiculo",
            "vehiculo_placa",
            "vehiculo_numero",
            "vehiculo_descripcion",
            "kilometraje_inicial",
            "kilometraje_final",
            "kilometros_recorridos",
            "ingreso_bruto",
            "porcentaje_pago_conductor",
            "pago_conductor",
            "total_adelantos",
            "pago_pendiente_conductor",
            "saldo_adelanto_excedente",
            "total_gastos",
            "ganancia_dueno",
            "observaciones",
            "fecha_registro",
            "gastos",
        ]

        read_only_fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "estado_nombre",
            "estado_codigo",
            "conductor_nombre",
            "vehiculo_placa",
            "vehiculo_numero",
            "vehiculo_descripcion",
            "kilometros_recorridos",
            "pago_conductor",
            "total_adelantos",
            "pago_pendiente_conductor",
            "saldo_adelanto_excedente",
            "total_gastos",
            "ganancia_dueno",
            "fecha_registro",
            "gastos",
        ]

        extra_kwargs = {
            "estado": {
                "required": False,
                "allow_null": True,
            },
            "kilometraje_inicial": {
                "required": True,
            },
            "kilometraje_final": {
                "required": False,
                "allow_null": True,
            },
            "ingreso_bruto": {
                "required": False,
            },
            "observaciones": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
        }

    def get_sucursal_nombre(self, obj):
        return obj.sucursal.nombre if obj.sucursal else ""

    def get_conductor_nombre(self, obj):
        if not obj.conductor:
            return ""

        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def get_vehiculo_placa(self, obj):
        return obj.vehiculo.placa if obj.vehiculo else ""

    def get_vehiculo_numero(self, obj):
        return obj.vehiculo.numero if obj.vehiculo else ""

    def get_vehiculo_descripcion(self, obj):
        if not obj.vehiculo:
            return ""

        return f"{obj.vehiculo.numero} - {obj.vehiculo.placa} - {obj.vehiculo.marca} {obj.vehiculo.modelo}"

    def get_estado_nombre(self, obj):
        return obj.estado.nombre if obj.estado else ""

    def get_estado_codigo(self, obj):
        return obj.estado.codigo if obj.estado else ""

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        kilometraje_inicial = attrs.get(
            "kilometraje_inicial",
            getattr(self.instance, "kilometraje_inicial", None)
        )

        kilometraje_final = attrs.get(
            "kilometraje_final",
            getattr(self.instance, "kilometraje_final", None)
        )

        if kilometraje_inicial is not None and kilometraje_final is not None:
            if kilometraje_final < kilometraje_inicial:
                raise serializers.ValidationError({
                    "kilometraje_final": "El kilometraje final no puede ser menor al kilometraje inicial."
                })

        conductor = attrs.get(
            "conductor",
            getattr(self.instance, "conductor", None)
        )

        vehiculo = attrs.get(
            "vehiculo",
            getattr(self.instance, "vehiculo", None)
        )

        if not user or not user.rol:
            raise serializers.ValidationError(
                "No se pudo validar el usuario autenticado."
            )

        codigo_rol = user.rol.codigo

        if codigo_rol == "taxista":
            try:
                conductor_usuario = user.perfil_conductor
            except Conductor.DoesNotExist:
                raise serializers.ValidationError({
                    "conductor": "Este usuario no tiene perfil de conductor."
                })

            conductor = conductor_usuario
            attrs["conductor"] = conductor_usuario

        if not conductor:
            raise serializers.ValidationError({
                "conductor": "Debes seleccionar un conductor."
            })

        if not vehiculo:
            raise serializers.ValidationError({
                "vehiculo": "Debes seleccionar un vehículo."
            })

        if codigo_rol in ["superadmin", "super_admin"]:
            attrs["sucursal"] = conductor.sucursal

        elif codigo_rol == "admin_sucursal":
            if not user.sucursal:
                raise serializers.ValidationError({
                    "sucursal": "Tu usuario no tiene una sucursal asignada."
                })

            if conductor.sucursal_id != user.sucursal_id:
                raise serializers.ValidationError({
                    "conductor": "No puedes registrar jornadas para conductores de otra sucursal."
                })

            if vehiculo.sucursal_id != user.sucursal_id:
                raise serializers.ValidationError({
                    "vehiculo": "No puedes registrar jornadas para vehículos de otra sucursal."
                })

            attrs["sucursal"] = user.sucursal

        elif codigo_rol == "taxista":
            if conductor.usuario_id != user.id:
                raise serializers.ValidationError({
                    "conductor": "No puedes registrar jornadas para otro conductor."
                })

            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise serializers.ValidationError({
                    "vehiculo": "El vehículo no pertenece al mismo entorno que el conductor."
                })

            attrs["sucursal"] = conductor.sucursal

        else:
            raise serializers.ValidationError(
                "No tienes permiso para registrar jornadas."
            )

        asignacion_activa = AsignacionVehiculo.objects.filter(
            conductor=conductor,
            vehiculo=vehiculo,
            activa=True
        )

        if codigo_rol in ["superadmin", "super_admin"]:
            asignacion_activa = asignacion_activa.filter(
                sucursal=conductor.sucursal
            )

        elif codigo_rol in ["admin_sucursal", "taxista"]:
            asignacion_activa = asignacion_activa.filter(
                sucursal=conductor.sucursal
            )

        if not asignacion_activa.exists():
            raise serializers.ValidationError({
                "vehiculo": "El conductor no tiene una asignación activa con ese vehículo."
            })

        return attrs


class MantenimientoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    tipo_mantenimiento_nombre = serializers.CharField(source="tipo_mantenimiento.nombre", read_only=True)
    tipo_mantenimiento_codigo = serializers.CharField(source="tipo_mantenimiento.codigo", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    estado_codigo = serializers.CharField(source="estado.codigo", read_only=True)

    class Meta:
        model = Mantenimiento
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "vehiculo",
            "vehiculo_placa",
            "tipo_mantenimiento",
            "tipo_mantenimiento_nombre",
            "tipo_mantenimiento_codigo",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "descripcion",
            "costo",
            "fecha",
            "kilometraje",
            "proximo_km_sugerido",
        ]
        read_only_fields = [
            "id",
            "sucursal_nombre",
            "vehiculo_placa",
            "tipo_mantenimiento_nombre",
            "tipo_mantenimiento_codigo",
            "estado_nombre",
            "estado_codigo",
        ]

    def validate(self, attrs):
        sucursal = attrs.get("sucursal", getattr(self.instance, "sucursal", None))
        vehiculo = attrs.get("vehiculo", getattr(self.instance, "vehiculo", None))

        if sucursal and vehiculo and sucursal.id != vehiculo.sucursal_id:
            raise serializers.ValidationError("El vehículo no pertenece a la sucursal indicada.")

        return attrs


class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

    class Meta:
        model = ConfiguracionSistema
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "porcentaje_pago_conductor",
            "intervalo_cambio_aceite_km",
            "intervalo_mantenimiento_km",
            "alerta_previa_km",
            "moneda",
        ]
        read_only_fields = ["id", "sucursal_nombre"]


class LiquidacionConductorSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    conductor_nombre = serializers.SerializerMethodField()
    conductor_cedula = serializers.CharField(source="conductor.cedula", read_only=True)

    class Meta:
        model = LiquidacionConductor
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "conductor",
            "conductor_nombre",
            "conductor_cedula",
            "fecha_inicio",
            "fecha_fin",
            "total_jornadas",
            "total_adelantos_pendientes",
            "abono_aplicado",
            "ajuste_manual",
            "total_pago",
            "notas",
            "fecha_creacion",
        ]

        read_only_fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "conductor_nombre",
            "conductor_cedula",
            "fecha_inicio",
            "fecha_fin",
            "total_jornadas",
            "total_adelantos_pendientes",
            "total_pago",
            "fecha_creacion",
        ]

    def get_conductor_nombre(self, obj):
        if not obj.conductor:
            return ""
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def validate(self, attrs):
        ajuste_manual = attrs.get(
            "ajuste_manual",
            getattr(self.instance, "ajuste_manual", Decimal("0.00"))
        )

        abono_aplicado = attrs.get(
            "abono_aplicado",
            getattr(self.instance, "abono_aplicado", Decimal("0.00"))
        )

        if ajuste_manual is not None and ajuste_manual < Decimal("0.00"):
            raise serializers.ValidationError({
                "ajuste_manual": "El ajuste manual no puede ser negativo."
            })

        if abono_aplicado is not None and abono_aplicado < Decimal("0.00"):
            raise serializers.ValidationError({
                "abono_aplicado": "El abono aplicado no puede ser negativo."
            })

        return attrs