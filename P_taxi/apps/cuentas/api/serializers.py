"""Serializadores de cuentas móviles."""
from datetime import date

from django.contrib.auth.password_validation import (
    validate_password,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from App_taxi.models import (
    Conductor,
    Rol,
    Usuario,
    Vehiculo,
)
from apps.flota.models import TipoVehiculo

from ..models import InvitacionConductor


def normalizar_telefono(value):
    telefono_original = str(
        value or ""
    ).strip()

    tiene_prefijo = (
        telefono_original.startswith("+")
    )

    numeros = "".join(
        caracter
        for caracter in telefono_original
        if caracter.isdigit()
    )

    return (
        f"+{numeros}"
        if tiene_prefijo
        else numeros
    )


def normalizar_identificacion(value):
    return "".join(
        caracter.lower()
        for caracter in str(
            value or ""
        )
        if caracter.isalnum()
    )


class ActivarConductorSerializer(
    serializers.Serializer
):
    token_invitacion = serializers.UUIDField()

    telefono = serializers.CharField(
        max_length=20,
    )

    cedula = serializers.CharField(
        max_length=30,
    )

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    confirmar_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    def validate(self, attrs):
        token_invitacion = attrs.get(
            "token_invitacion"
        )

        telefono = normalizar_telefono(
            attrs.get("telefono")
        )

        cedula = normalizar_identificacion(
            attrs.get("cedula")
        )

        if len(
            "".join(
                caracter
                for caracter in telefono
                if caracter.isdigit()
            )
        ) < 8:
            raise serializers.ValidationError(
                {
                    "telefono": (
                        "Debes ingresar un número "
                        "de teléfono válido."
                    )
                }
            )

        if not cedula:
            raise serializers.ValidationError(
                {
                    "cedula": (
                        "Debes ingresar la cédula."
                    )
                }
            )

        try:
            invitacion = (
                InvitacionConductor.objects
                .select_related(
                    "conductor",
                    "conductor__usuario",
                    "conductor__sucursal",
                )
                .get(
                    token=token_invitacion
                )
            )
        except InvitacionConductor.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "token_invitacion": (
                        "El código de invitación "
                        "no es válido."
                    )
                }
            )

        if not invitacion.es_valida:
            raise serializers.ValidationError(
                {
                    "token_invitacion": (
                        "La invitación está vencida, "
                        "utilizada o desactivada."
                    )
                }
            )

        conductor = invitacion.conductor

        if not conductor.activo:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Este conductor no se "
                        "encuentra activo."
                    )
                }
            )

        if conductor.usuario_id:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Este conductor ya tiene "
                        "una cuenta vinculada."
                    )
                }
            )

        telefono_conductor = (
            normalizar_telefono(
                conductor.telefono
            )
        )

        cedula_conductor = (
            normalizar_identificacion(
                conductor.cedula
            )
        )

        if (
            not telefono_conductor
            or telefono
            != telefono_conductor
        ):
            raise serializers.ValidationError(
                {
                    "telefono": (
                        "El teléfono no coincide "
                        "con el registro del conductor."
                    )
                }
            )

        if cedula != cedula_conductor:
            raise serializers.ValidationError(
                {
                    "cedula": (
                        "La cédula no coincide "
                        "con el registro del conductor."
                    )
                }
            )

        usuario_existente = (
            Usuario.objects
            .filter(
                Q(username=telefono)
                | Q(telefono=telefono)
            )
            .exists()
        )

        if usuario_existente:
            raise serializers.ValidationError(
                {
                    "telefono": (
                        "Ya existe una cuenta "
                        "registrada con este teléfono."
                    )
                }
            )

        password = attrs.get("password")

        confirmar_password = attrs.get(
            "confirmar_password"
        )

        if password != confirmar_password:
            raise serializers.ValidationError(
                {
                    "confirmar_password": (
                        "Las contraseñas no coinciden."
                    )
                }
            )

        try:
            validate_password(password)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {
                    "password": list(
                        error.messages
                    )
                }
            )

        attrs["telefono"] = telefono
        attrs["invitacion"] = invitacion

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        invitacion_original = (
            validated_data.pop(
                "invitacion"
            )
        )

        token_invitacion = (
            validated_data.pop(
                "token_invitacion"
            )
        )

        password = validated_data.pop(
            "password"
        )

        validated_data.pop(
            "confirmar_password"
        )

        telefono = validated_data.pop(
            "telefono"
        )

        validated_data.pop(
            "cedula"
        )

        invitacion = (
            InvitacionConductor.objects
            .select_for_update()
            .select_related(
                "conductor",
                "conductor__sucursal",
            )
            .get(
                pk=invitacion_original.pk,
                token=token_invitacion,
            )
        )

        if not invitacion.es_valida:
            raise serializers.ValidationError(
                {
                    "token_invitacion": (
                        "La invitación ya no "
                        "está disponible."
                    )
                }
            )

        conductor = invitacion.conductor

        if conductor.usuario_id:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Este conductor ya tiene "
                        "una cuenta vinculada."
                    )
                }
            )

        try:
            rol_taxista = Rol.objects.get(
                codigo="taxista",
                activo=True,
            )
        except Rol.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "El rol taxista no está "
                        "configurado en el sistema."
                    )
                }
            )

        usuario = Usuario.objects.create_user(
            username=telefono,
            first_name=conductor.nombre,
            last_name=conductor.apellido,
            telefono=telefono,
            rol=rol_taxista,
            sucursal=conductor.sucursal,
            password=password,
            is_active=True,
        )

        conductor.usuario = usuario

        conductor.save(
            update_fields=[
                "usuario",
            ]
        )

        invitacion.marcar_utilizada()

        return conductor
    

class RegistroVehiculoConductorSerializer(
    serializers.Serializer
):
    tipo_vehiculo_id = serializers.PrimaryKeyRelatedField(
        source="tipo_vehiculo",
        queryset=TipoVehiculo.objects.filter(activo=True),
    )
    placa = serializers.CharField(max_length=20)
    marca = serializers.CharField(max_length=50)
    modelo = serializers.CharField(max_length=50)
    anio = serializers.IntegerField(
        min_value=1900,
        max_value=date.today().year + 1,
    )
    color = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default="",
    )
    numero_motor = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    numero_chasis = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    tipo_combustible = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default="",
    )
    kilometraje_actual = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
    )

    def validate_placa(self, value):
        placa = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "")
        )

        if not placa:
            raise serializers.ValidationError(
                "La placa es obligatoria."
            )

        if Vehiculo.objects.filter(
            placa__iexact=placa
        ).exists():
            raise serializers.ValidationError(
                "Ya existe un vehículo registrado con esta placa."
            )

        return placa


class RegistroConductorSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    telefono = serializers.CharField(max_length=20)
    cedula = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    confirmar_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    vehiculo = RegistroVehiculoConductorSerializer()

    def validate_telefono(self, telefono):
        telefono = telefono.strip()

        if Usuario.objects.filter(username=telefono).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta registrada con este teléfono."
            )

        if Conductor.objects.filter(telefono=telefono).exists():
            raise serializers.ValidationError(
                "Este conductor ya existe en el sistema. Debe activar su cuenta mediante una invitación."
            )

        return telefono

    def validate_cedula(self, cedula):
        cedula = cedula.strip()

        if Conductor.objects.filter(cedula__iexact=cedula).exists():
            raise serializers.ValidationError(
                "Esta cédula ya pertenece a un conductor registrado."
            )

        return cedula

    def validate(self, datos):
        password = datos.get("password")
        confirmar_password = datos.get("confirmar_password")

        if password != confirmar_password:
            raise serializers.ValidationError({
                "confirmar_password": "Las contraseñas no coinciden."
            })

        validate_password(password)

        return datos

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("confirmar_password")

        password = validated_data.pop("password")
        email = validated_data.pop("email", "")
        vehiculo_data = validated_data.pop("vehiculo")
        telefono = validated_data["telefono"]

        rol_taxista = Rol.objects.get(codigo="taxista")

        usuario = Usuario.objects.create_user(
            username=telefono,
            password=password,
            first_name=validated_data["nombre"],
            last_name=validated_data["apellido"],
            email=email,
            telefono=telefono,
            rol=rol_taxista,
            sucursal=None,
            is_active=True,
        )

        conductor = Conductor.objects.create(
            usuario=usuario,
            sucursal=None,
            nombre=validated_data["nombre"],
            apellido=validated_data["apellido"],
            telefono=telefono,
            cedula=validated_data["cedula"],
            estado_verificacion="pendiente",
            activo=False,
        )

        tipo_vehiculo = vehiculo_data.pop(
            "tipo_vehiculo"
        )
        placa = vehiculo_data["placa"]

        vehiculo = Vehiculo.objects.create(
            sucursal=conductor.sucursal,
            estado=None,
            tipo_vehiculo=tipo_vehiculo,
            tipo_propiedad="conductor",
            propietario_conductor=conductor,
            estado_verificacion="pendiente",
            motivo_rechazo="",
            numero=placa,
            placa=placa,
            marca=vehiculo_data["marca"],
            modelo=vehiculo_data["modelo"],
            anio=vehiculo_data["anio"],
            color=vehiculo_data.get("color", ""),
            numero_motor=vehiculo_data.get(
                "numero_motor",
                "",
            ),
            numero_chasis=vehiculo_data.get(
                "numero_chasis",
                "",
            ),
            tipo_combustible=vehiculo_data.get(
                "tipo_combustible",
                "",
            ),
            kilometraje_actual=vehiculo_data.get(
                "kilometraje_actual",
                0,
            ),
        )

        conductor.vehiculo_registrado = vehiculo

        return conductor
