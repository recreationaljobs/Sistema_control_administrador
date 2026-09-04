"""Disponibilidad y ubicación actual."""

from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction
from django.utils import timezone

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
)
from apps.viajes.models import Viaje

from .models import (
    EstadoConductorTiempoReal,
)



ESTADOS_CONDUCTOR_EN_VIAJE = [
    "aceptado",
    "conductor_en_camino",
    "conductor_llego",
    "en_curso",
]


def obtener_conductor_habilitado(
    usuario,
):
    conductor = (
        Conductor.objects
        .select_related("usuario")
        .filter(
            usuario=usuario,
            estado_verificacion="aprobado",
            activo=True,
        )
        .first()
    )

    if not conductor:
        raise ValidationError(
            "La cuenta no tiene un conductor "
            "aprobado y activo."
        )

    asignacion = (
        AsignacionVehiculo.objects
        .select_related("vehiculo")
        .filter(
            conductor=conductor,
            activa=True,
            vehiculo__estado_verificacion=(
                "aprobado"
            ),
        )
        .first()
    )

    if not asignacion:
        raise ValidationError(
            "El conductor no tiene un "
            "vehículo aprobado y asignado."
        )

    return conductor


@transaction.atomic
def cambiar_disponibilidad(
    usuario,
    disponible,
):
    conductor = obtener_conductor_habilitado(
        usuario
    )

    conductor = (
        Conductor.objects
        .select_for_update()
        .get(pk=conductor.pk)
    )

    viaje_actual = (
        Viaje.objects
        .filter(
            conductor=conductor,
            estado__in=(
                ESTADOS_CONDUCTOR_EN_VIAJE
            ),
        )
        .first()
    )

    if disponible and viaje_actual:
        raise ValidationError(
            "No puedes marcarte disponible "
            "mientras tienes un viaje activo."
        )

    estado, _ = (
        EstadoConductorTiempoReal.objects
        .get_or_create(
            conductor=conductor
        )
    )

    estado.en_linea = True
    estado.disponible = disponible
    estado.viaje_actual = viaje_actual
    estado.ultima_conexion = timezone.now()

    estado.save(
        update_fields=[
            "en_linea",
            "disponible",
            "viaje_actual",
            "ultima_conexion",
            "fecha_actualizacion",
        ]
    )

    return estado


@transaction.atomic
def actualizar_ubicacion(
    usuario,
    latitud,
    longitud,
    precision_metros=None,
    velocidad_kmh=None,
    rumbo_grados=None,
):
    conductor = obtener_conductor_habilitado(
        usuario
    )

    conductor = (
        Conductor.objects
        .select_for_update()
        .get(pk=conductor.pk)
    )

    viaje_actual = (
        Viaje.objects
        .filter(
            conductor=conductor,
            estado__in=(
                ESTADOS_CONDUCTOR_EN_VIAJE
            ),
        )
        .first()
    )

    estado, _ = (
        EstadoConductorTiempoReal.objects
        .get_or_create(
            conductor=conductor
        )
    )

    estado.en_linea = True
    estado.viaje_actual = viaje_actual
    estado.latitud = latitud
    estado.longitud = longitud
    estado.precision_metros = (
        precision_metros
    )
    estado.velocidad_kmh = velocidad_kmh
    estado.rumbo_grados = rumbo_grados
    estado.ultima_conexion = timezone.now()
    estado.ultima_ubicacion = timezone.now()

    if viaje_actual:
        estado.disponible = False

    estado.save(
        update_fields=[
            "en_linea",
            "disponible",
            "viaje_actual",
            "latitud",
            "longitud",
            "precision_metros",
            "velocidad_kmh",
            "rumbo_grados",
            "ultima_conexion",
            "ultima_ubicacion",
            "fecha_actualizacion",
        ]
    )

    return estado

def marcar_conductor_en_viaje(
    conductor,
    viaje,
):
    estado, _ = (
        EstadoConductorTiempoReal.objects
        .get_or_create(
            conductor=conductor
        )
    )

    estado.en_linea = True
    estado.disponible = False
    estado.viaje_actual = viaje
    estado.ultima_conexion = timezone.now()

    estado.save(
        update_fields=[
            "en_linea",
            "disponible",
            "viaje_actual",
            "ultima_conexion",
            "fecha_actualizacion",
        ]
    )

    return estado


def liberar_estado_conductor(
    conductor,
):
    estado = (
        EstadoConductorTiempoReal.objects
        .filter(
            conductor=conductor
        )
        .first()
    )

    if not estado:
        return None

    estado.viaje_actual = None

    # Si continúa conectado, vuelve a estar
    # disponible para recibir solicitudes.
    estado.disponible = estado.en_linea
    estado.ultima_conexion = timezone.now()

    estado.save(
        update_fields=[
            "disponible",
            "viaje_actual",
            "ultima_conexion",
            "fecha_actualizacion",
        ]
    )

    return estado

TIEMPO_EXPIRACION_SEGUNDOS = 90


def validar_conductor_disponible(
    conductor,
):
    estado = (
        EstadoConductorTiempoReal.objects
        .filter(
            conductor=conductor
        )
        .first()
    )

    if not estado:
        raise ValidationError(
            "El conductor todavía no se "
            "ha conectado."
        )

    if (
        not estado.en_linea
        or not estado.disponible
    ):
        raise ValidationError(
            "El conductor no está disponible."
        )

    if not estado.ultima_conexion:
        raise ValidationError(
            "No existe una conexión reciente "
            "del conductor."
        )

    segundos = (
        timezone.now()
        - estado.ultima_conexion
    ).total_seconds()

    if segundos > TIEMPO_EXPIRACION_SEGUNDOS:
        estado.en_linea = False
        estado.disponible = False

        estado.save(
            update_fields=[
                "en_linea",
                "disponible",
                "fecha_actualizacion",
            ]
        )

        raise ValidationError(
            "La conexión del conductor expiró. "
            "Debe conectarse nuevamente."
        )

    return estado


@transaction.atomic
def desconectar_conductor(
    usuario,
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .filter(
            usuario=usuario
        )
        .first()
    )

    if not conductor:
        raise ValidationError(
            "La cuenta no tiene un perfil "
            "de conductor."
        )

    viaje_activo = (
        Viaje.objects
        .filter(
            conductor=conductor,
            estado__in=(
                ESTADOS_CONDUCTOR_EN_VIAJE
            ),
        )
        .exists()
    )

    if viaje_activo:
        raise ValidationError(
            "No puedes desconectarte mientras "
            "tienes un viaje activo."
        )

    estado, _ = (
        EstadoConductorTiempoReal.objects
        .get_or_create(
            conductor=conductor
        )
    )

    estado.en_linea = False
    estado.disponible = False
    estado.viaje_actual = None
    estado.ultima_conexion = timezone.now()

    estado.save(
        update_fields=[
            "en_linea",
            "disponible",
            "viaje_actual",
            "ultima_conexion",
            "fecha_actualizacion",
        ]
    )

    return estado