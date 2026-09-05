from django.contrib.auth.password_validation import (
    validate_password,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from rest_framework import serializers


class SolicitarCodigoPasswordSerializer(
    serializers.Serializer
):
    identificador = serializers.CharField(
        max_length=254,
    )

    def validate_identificador(self, value):
        identificador = str(value).strip()

        if not identificador:
            raise serializers.ValidationError(
                "Ingresa tu usuario, correo "
                "o teléfono."
            )

        return identificador


class RestablecerPasswordSerializer(
    serializers.Serializer
):
    identificador = serializers.CharField(
        max_length=254,
    )

    codigo = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={
            "invalid": (
                "El código debe contener "
                "seis números."
            ),
        },
    )

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )

    confirmar_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )

    def validate_identificador(self, value):
        return str(value).strip()

    def validate(self, attrs):
        password = attrs["password"]

        if password != attrs["confirmar_password"]:
            raise serializers.ValidationError({
                "confirmar_password": (
                    "Las contraseñas no coinciden."
                )
            })

        try:
            validate_password(password)
        except DjangoValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages
            }) from error

        return attrs