
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.db.models.signals import (
    post_delete,
    post_save,
    pre_save,
)
from django.dispatch import receiver

from .auditoria_contexto import obtener_request
from .models import (
    Adelanto,
    AsignacionVehiculo,
    Conductor,
    ConfiguracionSistema,
    DocumentoVehiculo,
    Gasto,
    JornadaDiaria,
    Liquidacion,
    Mantenimiento,
    MovimientoAuditoria,
    Rol,
    Sucursal,
    Usuario,
    Vehiculo,
)


MODELOS_AUDITADOS = (
    Sucursal,
    Rol,
    Usuario,
    Conductor,
    Vehiculo,
    DocumentoVehiculo,
    AsignacionVehiculo,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Mantenimiento,
    ConfiguracionSistema,
    Liquidacion,
)

CAMPOS_OCULTOS = {
    "password",
    "last_login",
    "is_superuser",
    "user_permissions",
    "groups",
}


def convertir_valor(valor):
    if valor is None:
        return None

    if isinstance(valor, (Decimal, UUID)):
        return str(valor)

    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()

    if isinstance(valor, dict):
        return {
            str(clave): convertir_valor(dato)
            for clave, dato in valor.items()
        }

    if isinstance(valor, (list, tuple)):
        return [
            convertir_valor(dato)
            for dato in valor
        ]

    return valor


def obtener_datos_instancia(instancia):
    datos = {}

    for campo in instancia._meta.concrete_fields:
        if campo.name in CAMPOS_OCULTOS:
            continue

        try:
            valor = getattr(instancia, campo.attname)
        except Exception:
            continue

        datos[campo.name] = convertir_valor(valor)

    return datos


def obtener_ip(request):
    if not request:
        return None

    ip_reenviada = request.META.get("HTTP_X_FORWARDED_FOR")

    if ip_reenviada:
        return ip_reenviada.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def obtener_usuario_actual():
    request = obtener_request()

    if not request:
        return None, None

    usuario = getattr(request, "user", None)

    if not usuario or not usuario.is_authenticated:
        return None, request

    return usuario, request


def registrar_movimiento(
    *,
    accion,
    modulo,
    descripcion,
    objeto_id=None,
    datos_anteriores=None,
    datos_nuevos=None,
    usuario=None,
    request=None,
):
    if usuario is None:
        usuario_contexto, request_contexto = obtener_usuario_actual()
        usuario = usuario_contexto
        request = request or request_contexto

    if not usuario or not usuario.is_authenticated:
        return

    sucursal = getattr(usuario, "sucursal", None)

    MovimientoAuditoria.objects.create(
        usuario=usuario,
        sucursal=sucursal,
        accion=accion,
        modulo=modulo,
        descripcion=descripcion,
        objeto_id=objeto_id,
        datos_anteriores=datos_anteriores or {},
        datos_nuevos=datos_nuevos or {},
        direccion_ip=obtener_ip(request),
    )


@receiver(pre_save)
def guardar_datos_anteriores(sender, instance, **kwargs):
    if sender not in MODELOS_AUDITADOS:
        return

    if not instance.pk:
        instance._auditoria_antes = {}
        return

    try:
        anterior = sender.objects.get(pk=instance.pk)
        instance._auditoria_antes = obtener_datos_instancia(anterior)
    except sender.DoesNotExist:
        instance._auditoria_antes = {}


@receiver(post_save)
def registrar_guardado(sender, instance, created, **kwargs):
    if sender not in MODELOS_AUDITADOS:
        return

    usuario, request = obtener_usuario_actual()

    if not usuario:
        return

    modulo = sender._meta.verbose_name_plural.capitalize()
    datos_actuales = obtener_datos_instancia(instance)

    if created:
        registrar_movimiento(
            accion=MovimientoAuditoria.ACCION_CREAR,
            modulo=modulo,
            descripcion=(
                f"Creó un registro en {modulo} "
                f"(ID: {instance.pk})."
            ),
            objeto_id=instance.pk,
            datos_nuevos=datos_actuales,
            usuario=usuario,
            request=request,
        )
        return

    datos_anteriores = getattr(
        instance,
        "_auditoria_antes",
        {},
    )

    cambios_anteriores = {}
    cambios_nuevos = {}

    for campo, valor_nuevo in datos_actuales.items():
        valor_anterior = datos_anteriores.get(campo)

        if valor_anterior != valor_nuevo:
            cambios_anteriores[campo] = valor_anterior
            cambios_nuevos[campo] = valor_nuevo

    if not cambios_nuevos:
        return

    registrar_movimiento(
        accion=MovimientoAuditoria.ACCION_EDITAR,
        modulo=modulo,
        descripcion=(
            f"Editó un registro en {modulo} "
            f"(ID: {instance.pk})."
        ),
        objeto_id=instance.pk,
        datos_anteriores=cambios_anteriores,
        datos_nuevos=cambios_nuevos,
        usuario=usuario,
        request=request,
    )


@receiver(post_delete)
def registrar_eliminacion(sender, instance, **kwargs):
    if sender not in MODELOS_AUDITADOS:
        return

    usuario, request = obtener_usuario_actual()

    if not usuario:
        return

    modulo = sender._meta.verbose_name_plural.capitalize()
    datos_eliminados = obtener_datos_instancia(instance)

    registrar_movimiento(
        accion=MovimientoAuditoria.ACCION_ELIMINAR,
        modulo=modulo,
        descripcion=(
            f"Eliminó un registro en {modulo} "
            f"(ID: {instance.pk})."
        ),
        objeto_id=instance.pk,
        datos_anteriores=datos_eliminados,
        usuario=usuario,
        request=request,
    )