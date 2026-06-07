from rest_framework import serializers

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


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True)
    rol_codigo = serializers.CharField(source="rol.codigo", read_only=True)
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

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
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "rol_nombre",
            "rol_codigo",
            "sucursal_nombre",
            "date_joined",
            "is_staff",
            "is_superuser",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None)

        user = Usuario(**validated_data)

        if password:
            user.set_password(password)
        else:
            user.set_password("12345678")

        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class ConductorSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Conductor
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "usuario",
            "usuario_username",
            "usuario_email",
            "nombre",
            "apellido",
            "nombre_completo",
            "telefono",
            "cedula",
            "direccion",
            "licencia",
            "vencimiento_licencia",
            "porcentaje_pago",
            "fecha_registro",
            "activo",
        ]
        read_only_fields = [
            "id",
            "sucursal_nombre",
            "usuario_username",
            "usuario_email",
            "nombre_completo",
            "fecha_registro",
        ]

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}".strip()


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
        ]

    def get_conductor_nombre(self, obj):
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def validate(self, attrs):
        conductor = attrs.get("conductor", getattr(self.instance, "conductor", None))
        vehiculo = attrs.get("vehiculo", getattr(self.instance, "vehiculo", None))
        sucursal = attrs.get("sucursal", getattr(self.instance, "sucursal", None))
        activa = attrs.get("activa", getattr(self.instance, "activa", True))

        if conductor and vehiculo and conductor.sucursal_id != vehiculo.sucursal_id:
            raise serializers.ValidationError(
                "El conductor y el vehículo deben pertenecer a la misma sucursal."
            )

        if sucursal and conductor and conductor.sucursal_id != sucursal.id:
            raise serializers.ValidationError(
                "El conductor no pertenece a la sucursal indicada."
            )

        if sucursal and vehiculo and vehiculo.sucursal_id != sucursal.id:
            raise serializers.ValidationError(
                "El vehículo no pertenece a la sucursal indicada."
            )

        if activa:
            qs_vehiculo = AsignacionVehiculo.objects.filter(vehiculo=vehiculo, activa=True)
            qs_conductor = AsignacionVehiculo.objects.filter(conductor=conductor, activa=True)

            if self.instance:
                qs_vehiculo = qs_vehiculo.exclude(pk=self.instance.pk)
                qs_conductor = qs_conductor.exclude(pk=self.instance.pk)

            if qs_vehiculo.exists():
                raise serializers.ValidationError("Ese vehículo ya tiene una asignación activa.")

            if qs_conductor.exists():
                raise serializers.ValidationError("Ese conductor ya tiene una asignación activa.")

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

    class Meta:
        model = Adelanto
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "jornada",
            "conductor",
            "conductor_nombre",
            "estado",
            "estado_nombre",
            "estado_codigo",
            "monto",
            "fecha",
            "observacion",
        ]
        read_only_fields = [
            "id",
            "sucursal_nombre",
            "conductor_nombre",
            "estado_nombre",
            "estado_codigo",
        ]

    def get_conductor_nombre(self, obj):
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def validate(self, attrs):
        jornada = attrs.get("jornada", getattr(self.instance, "jornada", None))
        conductor = attrs.get("conductor", getattr(self.instance, "conductor", None))
        sucursal = attrs.get("sucursal", getattr(self.instance, "sucursal", None))

        if jornada:
            if conductor and conductor.id != jornada.conductor_id:
                raise serializers.ValidationError("El conductor no coincide con la jornada.")

            if sucursal and sucursal.id != jornada.sucursal_id:
                raise serializers.ValidationError("La sucursal no coincide con la jornada.")

        return attrs


class JornadaDiariaSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    conductor_nombre = serializers.SerializerMethodField()
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    vehiculo_numero = serializers.CharField(source="vehiculo.numero", read_only=True)
    estado_nombre = serializers.CharField(source="estado.nombre", read_only=True)
    estado_codigo = serializers.CharField(source="estado.codigo", read_only=True)

    gastos = GastoSerializer(many=True, read_only=True)
    adelantos = AdelantoSerializer(many=True, read_only=True)

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
            "adelantos",
        ]
        read_only_fields = [
            "id",
            "sucursal_nombre",
            "estado_nombre",
            "estado_codigo",
            "conductor_nombre",
            "vehiculo_placa",
            "vehiculo_numero",
            "kilometros_recorridos",
            "pago_conductor",
            "total_adelantos",
            "pago_pendiente_conductor",
            "saldo_adelanto_excedente",
            "total_gastos",
            "ganancia_dueno",
            "fecha_registro",
            "gastos",
            "adelantos",
        ]

    def get_conductor_nombre(self, obj):
        return f"{obj.conductor.nombre} {obj.conductor.apellido}".strip()

    def validate(self, attrs):
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
                raise serializers.ValidationError(
                    "El kilometraje final no puede ser menor al kilometraje inicial."
                )

        conductor = attrs.get("conductor", getattr(self.instance, "conductor", None))
        vehiculo = attrs.get("vehiculo", getattr(self.instance, "vehiculo", None))
        sucursal = attrs.get("sucursal", getattr(self.instance, "sucursal", None))

        if conductor and vehiculo:
            if conductor.sucursal_id != vehiculo.sucursal_id:
                raise serializers.ValidationError(
                    "El conductor y el vehículo deben pertenecer a la misma sucursal."
                )

        if sucursal and conductor and sucursal.id != conductor.sucursal_id:
            raise serializers.ValidationError("El conductor no pertenece a la sucursal indicada.")

        if sucursal and vehiculo and sucursal.id != vehiculo.sucursal_id:
            raise serializers.ValidationError("El vehículo no pertenece a la sucursal indicada.")

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