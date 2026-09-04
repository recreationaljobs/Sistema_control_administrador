"""Serializadores de pasajeros."""
from django.contrib.auth.password_validation import (
    validate_password,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from App_taxi.models import Rol, Usuario

from ..models import Pasajero


class PasajeroSerializer(
    serializers.ModelSerializer
):
    usuario_id = serializers.IntegerField(
        source="usuario.id",
        read_only=True,
    )

    nombres = serializers.CharField(
        source="usuario.first_name",
        read_only=True,
    )

    apellidos = serializers.CharField(
        source="usuario.last_name",
        read_only=True,
    )

    telefono = serializers.CharField(
        source="usuario.telefono",
        read_only=True,
    )

    email = serializers.EmailField(
        source="usuario.email",
        read_only=True,
    )

    class Meta:
        model = Pasajero

        fields = [
            "id",
            "usuario_id",
            "nombres",
            "apellidos",
            "telefono",
            "email",
            "foto",
            "estado",
            "calificacion",
            "total_viajes",
            "fecha_registro",
            "fecha_actualizacion",
        ]

        read_only_fields = [
            "id",
            "usuario_id",
            "nombres",
            "apellidos",
            "telefono",
            "email",
            "estado",
            "calificacion",
            "total_viajes",
            "fecha_registro",
            "fecha_actualizacion",
        ]


class RegistroPasajeroSerializer(
    serializers.Serializer
):
    nombres = serializers.CharField(
        max_length=150,
    )

    apellidos = serializers.CharField(
        max_length=150,
    )

    telefono = serializers.CharField(
        max_length=20,
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
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

    def validate_nombres(self, value):
        nombres = value.strip()

        if len(nombres) < 2:
            raise serializers.ValidationError(
                "Debes ingresar un nombre válido."
            )

        return nombres

    def validate_apellidos(self, value):
        apellidos = value.strip()

        if len(apellidos) < 2:
            raise serializers.ValidationError(
                "Debes ingresar un apellido válido."
            )

        return apellidos

    def validate_telefono(self, value):
        telefono_original = value.strip()

        tiene_prefijo = (
            telefono_original.startswith("+")
        )

        numeros = "".join(
            caracter
            for caracter in telefono_original
            if caracter.isdigit()
        )

        if len(numeros) < 8:
            raise serializers.ValidationError(
                "El número de teléfono debe tener "
                "al menos 8 dígitos."
            )

        if len(numeros) > 15:
            raise serializers.ValidationError(
                "El número de teléfono no puede "
                "tener más de 15 dígitos."
            )

        telefono = (
            f"+{numeros}"
            if tiene_prefijo
            else numeros
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
                "Ya existe una cuenta registrada "
                "con este teléfono."
            )

        return telefono

    def validate_email(self, value):
        email = value.strip().lower()

        if not email:
            return ""

        if Usuario.objects.filter(
            email__iexact=email
        ).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta registrada "
                "con este correo electrónico."
            )

        return email

    def validate(self, attrs):
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

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop(
            "confirmar_password"
        )

        password = validated_data.pop(
            "password"
        )

        nombres = validated_data.pop(
            "nombres"
        )

        apellidos = validated_data.pop(
            "apellidos"
        )

        telefono = validated_data.pop(
            "telefono"
        )

        email = validated_data.pop(
            "email",
            "",
        )

        try:
            rol_pasajero = Rol.objects.get(
                codigo="pasajero",
                activo=True,
            )
        except Rol.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "El rol de pasajero no está "
                        "configurado en el sistema."
                    )
                }
            )

        usuario = Usuario.objects.create_user(
            username=telefono,
            first_name=nombres,
            last_name=apellidos,
            telefono=telefono,
            email=email,
            rol=rol_pasajero,
            password=password,
            is_active=True,
        )

        pasajero = Pasajero.objects.create(
            usuario=usuario,
        )

        return pasajero