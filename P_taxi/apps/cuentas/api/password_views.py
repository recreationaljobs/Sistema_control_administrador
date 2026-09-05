import secrets

from django.conf import settings
from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import (
    SimpleRateThrottle,
)
from rest_framework.views import APIView

from App_taxi.models import Usuario

from ..models import CodigoRecuperacionPassword
from .password_serializers import (
    RestablecerPasswordSerializer,
    SolicitarCodigoPasswordSerializer,
)


MENSAJE_SOLICITUD = (
    "Si la cuenta existe y tiene un correo "
    "registrado, recibirás un código "
    "de recuperación."
)


def obtener_usuario_por_identificador(
    identificador,
):
    identificador = str(
        identificador
    ).strip()

    usuario = (
        Usuario.objects
        .filter(
            username__iexact=identificador
        )
        .first()
    )

    if (
        usuario is None
        and "@" in identificador
    ):
        usuario = (
            Usuario.objects
            .filter(
                email__iexact=identificador
            )
            .exclude(email="")
            .order_by("id")
            .first()
        )

    if usuario is not None:
        return usuario

    digitos = "".join(
        caracter
        for caracter in identificador
        if caracter.isdigit()
    )

    variantes = {
        identificador,
    }

    if digitos:
        variantes.update({
            digitos,
            f"+{digitos}",
        })

        if len(digitos) == 8:
            variantes.update({
                f"505{digitos}",
                f"+505{digitos}",
            })

        if (
            len(digitos) == 11
            and digitos.startswith("505")
        ):
            variantes.update({
                digitos[-8:],
                f"+{digitos}",
            })

    consulta = Q()

    for telefono in variantes:
        consulta |= Q(
            telefono__iexact=telefono
        )

    return (
        Usuario.objects
        .filter(consulta)
        .order_by("id")
        .first()
    )


def obtener_ip(request):
    forwarded = request.META.get(
        "HTTP_X_FORWARDED_FOR",
        "",
    )

    if forwarded:
        return (
            forwarded
            .split(",")[0]
            .strip()
        )

    return request.META.get(
        "REMOTE_ADDR"
    )


class SolicitarCodigoPasswordThrottle(
    SimpleRateThrottle
):
    scope = "solicitar_codigo_password"
    rate = "5/hour"

    def get_cache_key(
        self,
        request,
        view,
    ):
        identificador = str(
            request.data.get(
                "identificador",
                "",
            )
        ).strip().lower()[:254]

        ident = (
            f"{self.get_ident(request)}:"
            f"{identificador}"
        )

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class RestablecerPasswordThrottle(
    SimpleRateThrottle
):
    scope = "restablecer_password"
    rate = "10/hour"

    def get_cache_key(
        self,
        request,
        view,
    ):
        return self.cache_format % {
            "scope": self.scope,
            "ident": (
                self.get_ident(request)
            ),
        }


class SolicitarCodigoPasswordView(
    APIView
):
    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    throttle_classes = [
        SolicitarCodigoPasswordThrottle,
    ]

    def post(self, request):
        serializer = (
            SolicitarCodigoPasswordSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        usuario = (
            obtener_usuario_por_identificador(
                serializer.validated_data[
                    "identificador"
                ]
            )
        )

        if (
            usuario is None
            or not str(
                usuario.email or ""
            ).strip()
        ):
            return Response(
                {
                    "mensaje": (
                        MENSAJE_SOLICITUD
                    )
                },
                status=status.HTTP_200_OK,
            )

        codigo = (
            f"{secrets.randbelow(1000000):06d}"
        )

        with transaction.atomic():
            (
                CodigoRecuperacionPassword
                .objects
                .filter(
                    usuario=usuario,
                    utilizado=False,
                )
                .update(
                    utilizado=True
                )
            )

            recuperacion = (
                CodigoRecuperacionPassword
                .objects
                .create(
                    usuario=usuario,
                    codigo_hash=make_password(
                        codigo
                    ),
                    ip_solicitud=obtener_ip(
                        request
                    ),
                )
            )

        try:
            send_mail(
                subject=(
                    "Código para recuperar "
                    "tu contraseña de Zenda"
                ),
                message=(
                    f"Hola "
                    f"{usuario.first_name or usuario.username},"
                    f"\n\n"
                    f"Tu código de recuperación es: "
                    f"{codigo}\n\n"
                    "El código vence en 10 minutos "
                    "y solo puede usarse una vez. "
                    "Si no solicitaste este cambio, "
                    "ignora este mensaje."
                ),
                from_email=(
                    settings.DEFAULT_FROM_EMAIL
                ),
                recipient_list=[
                    usuario.email,
                ],
                fail_silently=False,
            )
        except Exception:
            recuperacion.delete()

            return Response(
                {
                    "detail": (
                        "No fue posible enviar "
                        "el correo. Inténtalo "
                        "nuevamente más tarde."
                    )
                },
                status=(
                    status
                    .HTTP_503_SERVICE_UNAVAILABLE
                ),
            )

        return Response(
            {
                "mensaje": MENSAJE_SOLICITUD
            },
            status=status.HTTP_200_OK,
        )


class RestablecerPasswordView(
    APIView
):
    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    throttle_classes = [
        RestablecerPasswordThrottle,
    ]

    @transaction.atomic
    def post(self, request):
        serializer = (
            RestablecerPasswordSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        datos = serializer.validated_data

        usuario = (
            obtener_usuario_por_identificador(
                datos["identificador"]
            )
        )

        if usuario is None:
            return Response(
                {
                    "detail": (
                        "El código es inválido "
                        "o venció."
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        recuperacion = (
            CodigoRecuperacionPassword
            .objects
            .select_for_update()
            .filter(
                usuario=usuario,
                utilizado=False,
                fecha_vencimiento__gt=(
                    timezone.now()
                ),
            )
            .order_by(
                "-fecha_creacion"
            )
            .first()
        )

        if (
            recuperacion is None
            or recuperacion.intentos >= 5
        ):
            return Response(
                {
                    "detail": (
                        "El código es inválido "
                        "o venció."
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        codigo_correcto = check_password(
            datos["codigo"],
            recuperacion.codigo_hash,
        )

        if not codigo_correcto:
            recuperacion.intentos += 1

            if recuperacion.intentos >= 5:
                recuperacion.utilizado = True

            recuperacion.save(
                update_fields=[
                    "intentos",
                    "utilizado",
                ]
            )

            return Response(
                {
                    "detail": (
                        "El código es inválido "
                        "o venció."
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        usuario.set_password(
            datos["password"]
        )

        usuario.save(
            update_fields=[
                "password",
            ]
        )

        (
            CodigoRecuperacionPassword
            .objects
            .filter(
                usuario=usuario,
                utilizado=False,
            )
            .update(
                utilizado=True
            )
        )

        Token.objects.filter(
            user=usuario
        ).delete()

        return Response(
            {
                "mensaje": (
                    "La contraseña fue actualizada "
                    "correctamente. Ya puedes "
                    "iniciar sesión."
                )
            },
            status=status.HTTP_200_OK,
        )