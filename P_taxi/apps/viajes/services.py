"""Casos de uso de viajes."""

from decimal import Decimal

from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction

from apps.pasajeros.models import Pasajero
from django.utils import timezone

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
    EstadoVehiculo,
)
from apps.tarifas.services import (
    calcular_tarifa_estimada,
)
from apps.seguimiento.services import (
    liberar_estado_conductor,
    marcar_conductor_en_viaje,
    validar_conductor_disponible,
)

from .models import (
    HistorialEstadoViaje,
    OfertaViaje,
    PagoViaje,
    Viaje,
)
from .notificaciones import (
    programar_notificacion_viaje,
)


ESTADOS_VIAJE_ACTIVO = [
    "buscando_conductor",
    "aceptado",
    "conductor_en_camino",
    "conductor_llego",
    "en_curso",
]


@transaction.atomic
def solicitar_viaje(
    pasajero,
    tipo_vehiculo,
    origen_direccion,
    origen_latitud,
    origen_longitud,
    destino_direccion,
    destino_latitud,
    destino_longitud,
    tarifa_propuesta=None,
    metodo_pago="efectivo",
    notas_pasajero="",
):
    pasajero = (
        Pasajero.objects
        .select_for_update()
        .select_related("usuario")
        .get(pk=pasajero.pk)
    )

    viaje_activo = (
        Viaje.objects
        .filter(
            pasajero=pasajero,
            estado__in=ESTADOS_VIAJE_ACTIVO,
        )
        .first()
    )

    if viaje_activo:
        raise ValidationError(
            "Ya tienes un viaje activo. "
            "Debes finalizarlo o cancelarlo "
            "antes de solicitar otro."
        )

    if not tipo_vehiculo.activo:
        raise ValidationError(
            "El tipo de vehículo seleccionado "
            "no está disponible."
        )

    estimacion = calcular_tarifa_estimada(
        tipo_vehiculo=tipo_vehiculo,
        origen_latitud=origen_latitud,
        origen_longitud=origen_longitud,
        destino_latitud=destino_latitud,
        destino_longitud=destino_longitud,
        sucursal=None,
    )

    tarifa_estimada = Decimal(
        str(estimacion["tarifa_estimada"])
    ).quantize(Decimal("0.01"))

    if tarifa_propuesta is None:
        tarifa_acordada = tarifa_estimada
    else:
        tarifa_acordada = Decimal(
            str(tarifa_propuesta)
        ).quantize(Decimal("0.01"))

        if tarifa_acordada <= 0:
            raise ValidationError(
                "La tarifa propuesta debe ser "
                "mayor que cero."
            )

    viaje = Viaje.objects.create(
        pasajero=pasajero,
        tipo_vehiculo=tipo_vehiculo,
        estado="buscando_conductor",
        origen_direccion=origen_direccion,
        origen_latitud=origen_latitud,
        origen_longitud=origen_longitud,
        destino_direccion=destino_direccion,
        destino_latitud=destino_latitud,
        destino_longitud=destino_longitud,
        distancia_estimada_km=estimacion[
            "distancia_estimada_km"
        ],
        duracion_estimada_minutos=estimacion[
            "duracion_estimada_minutos"
        ],
        tarifa_estimada=tarifa_estimada,
        tarifa_acordada=tarifa_acordada,
        metodo_pago=metodo_pago,
        notas_pasajero=notas_pasajero,
    )

    HistorialEstadoViaje.objects.create(
        viaje=viaje,
        estado_anterior="",
        estado_nuevo="buscando_conductor",
        usuario=pasajero.usuario,
        observacion=(
            "Solicitud creada por el pasajero."
        ),
        latitud=origen_latitud,
        longitud=origen_longitud,
    )

    return viaje

@transaction.atomic
def aceptar_viaje(
    viaje_id,
    conductor,
    usuario,
    validar_disponibilidad=True,
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .select_related("sucursal")
        .get(pk=conductor.pk)
    )

    if (
        conductor.estado_verificacion
        != "aprobado"
        or not conductor.activo
    ):
        raise ValidationError(
            "El conductor no está aprobado "
            "o se encuentra inactivo."
        )

    if validar_disponibilidad:
        validar_conductor_disponible(
            conductor=conductor
        )

    asignacion = (
        AsignacionVehiculo.objects
        .select_for_update()
        .select_related(
            "vehiculo",
            "vehiculo__tipo_vehiculo",
        )
        .filter(
            conductor=conductor,
            activa=True,
        )
        .first()
    )

    if not asignacion:
        raise ValidationError(
            "El conductor no tiene un "
            "vehículo activo asignado."
        )

    vehiculo = asignacion.vehiculo

    if (
        vehiculo.estado_verificacion
        != "aprobado"
    ):
        raise ValidationError(
            "El vehículo no está aprobado."
        )

    if not vehiculo.tipo_vehiculo_id:
        raise ValidationError(
            "El vehículo no tiene un tipo "
            "configurado."
        )

    viaje_conductor_activo = (
        Viaje.objects
        .filter(
            conductor=conductor,
            estado__in=[
                "aceptado",
                "conductor_en_camino",
                "conductor_llego",
                "en_curso",
            ],
        )
        .exists()
    )

    if viaje_conductor_activo:
        raise ValidationError(
            "El conductor ya tiene "
            "un viaje activo."
        )

    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "tipo_vehiculo",
            )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje solicitado no existe."
        )

    if viaje.estado != "buscando_conductor":
        raise ValidationError(
            "El viaje ya no está disponible."
        )

    if (
        viaje.tipo_vehiculo_id
        != vehiculo.tipo_vehiculo_id
    ):
        raise ValidationError(
            "El tipo de vehículo no coincide "
            "con el solicitado por el pasajero."
        )

    estado_anterior = viaje.estado

    viaje.conductor = conductor
    viaje.vehiculo = vehiculo
    viaje.sucursal = (
        conductor.sucursal
        or vehiculo.sucursal
    )
    viaje.estado = "aceptado"
    viaje.fecha_aceptacion = timezone.now()

    if viaje.tarifa_acordada is None:
        viaje.tarifa_acordada = (
            viaje.tarifa_estimada
        )

    viaje.save(
        update_fields=[
            "conductor",
            "vehiculo",
            "sucursal",
            "estado",
            "fecha_aceptacion",
            "fecha_actualizacion",
            "tarifa_acordada",
        ]
    )

    OfertaViaje.objects.filter(
        viaje=viaje,
        estado="pendiente",
    ).update(
        estado="rechazada",
        fecha_respuesta=timezone.now(),
    )

    marcar_conductor_en_viaje(
        conductor=conductor,
        viaje=viaje,
    )

    HistorialEstadoViaje.objects.create(
        viaje=viaje,
        estado_anterior=estado_anterior,
        estado_nuevo="aceptado",
        usuario=usuario,
        observacion=(
            "Viaje aceptado por el conductor."
        ),
    )

    programar_notificacion_viaje(
        usuario=viaje.pasajero.usuario,
        titulo="Conductor encontrado",
        mensaje=(
            "Un conductor aceptó tu solicitud "
            "de viaje."
        ),
        tipo="viaje_aceptado",
        viaje_id=viaje.id,
    )

    return viaje

TRANSICIONES_CONDUCTOR = {
    "aceptado": "conductor_en_camino",
    "conductor_en_camino": "conductor_llego",
    "conductor_llego": "en_curso",
    "en_curso": "completado",
}


@transaction.atomic
def cambiar_estado_viaje_conductor(
    viaje_id,
    conductor,
    estado_nuevo,
    usuario,
    latitud=None,
    longitud=None,
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .get(pk=conductor.pk)
    )

    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                "conductor",
                "vehiculo",
                "pasajero",
                "pasajero__usuario",
            )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje no existe."
        )

    if viaje.conductor_id != conductor.id:
        raise ValidationError(
            "Este viaje no pertenece "
            "al conductor autenticado."
        )

    estado_permitido = (
        TRANSICIONES_CONDUCTOR.get(
            viaje.estado
        )
    )

    if not estado_permitido:
        raise ValidationError(
            "El viaje ya no permite cambios "
            "de estado del conductor."
        )

    if estado_nuevo != estado_permitido:
        raise ValidationError(
            (
                f"No puedes cambiar de "
                f"{viaje.estado} a "
                f"{estado_nuevo}. "
                f"El siguiente estado permitido "
                f"es {estado_permitido}."
            )
        )

    estado_anterior = viaje.estado
    viaje.estado = estado_nuevo

    campos_actualizados = [
        "estado",
        "fecha_actualizacion",
    ]

    if estado_nuevo == "conductor_llego":
        viaje.fecha_llegada_conductor = (
            timezone.now()
        )

        campos_actualizados.append(
            "fecha_llegada_conductor"
        )

    elif estado_nuevo == "en_curso":
        viaje.fecha_inicio = timezone.now()

        campos_actualizados.append(
            "fecha_inicio"
        )

    elif estado_nuevo == "completado":
        viaje.fecha_finalizacion = (
            timezone.now()
        )

        campos_actualizados.append(
            "fecha_finalizacion"
        )

        if viaje.tarifa_final is None:
            viaje.tarifa_final = (
                    viaje.tarifa_acordada
                    or viaje.tarifa_estimada
                )

            campos_actualizados.append(
                "tarifa_final"
            )

    viaje.save(
        update_fields=campos_actualizados
    )

    if estado_nuevo == "completado":
        if viaje.tarifa_final is None:
            raise ValidationError(
                "No se puede generar el pago "
                "porque el viaje no tiene "
                "una tarifa final."
            )

        PagoViaje.objects.get_or_create(
            viaje=viaje,
            defaults={
                "metodo": viaje.metodo_pago,
                "estado": (
                    PagoViaje
                    .ESTADO_PENDIENTE
                ),
                "moneda": "NIO",
                "monto": viaje.tarifa_final,
            },
        )

    if viaje.vehiculo_id:
        if estado_nuevo in [
            "conductor_en_camino",
            "conductor_llego",
            "en_curso",
        ]:
            estado_vehiculo = (
                EstadoVehiculo.objects
                .filter(
                    codigo="circulando",
                    activo=True,
                )
                .first()
            )

        else:
            estado_vehiculo = (
                EstadoVehiculo.objects
                .filter(
                    codigo="activo",
                    activo=True,
                )
                .first()
            )

        if estado_vehiculo:
            viaje.vehiculo.estado = (
                estado_vehiculo
            )

            viaje.vehiculo.save(
                update_fields=[
                    "estado",
                ]
            )

    HistorialEstadoViaje.objects.create(
        viaje=viaje,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        usuario=usuario,
        observacion=(
            "Estado actualizado por "
            "el conductor."
        ),
        latitud=latitud,
        longitud=longitud,
    )

    notificaciones_estado = {
        "conductor_en_camino": {
            "titulo": "Conductor en camino",
            "mensaje": (
                "Tu conductor se dirige hacia "
                "el punto de recogida."
            ),
            "tipo": "conductor_en_camino",
        },
        "conductor_llego": {
            "titulo": "El conductor llegó",
            "mensaje": (
                "Tu conductor ya se encuentra "
                "en el punto de recogida."
            ),
            "tipo": "conductor_llego",
        },
        "en_curso": {
            "titulo": "Viaje iniciado",
            "mensaje": (
                "Tu viaje ha comenzado."
            ),
            "tipo": "viaje_en_curso",
        },
        "completado": {
            "titulo": "Viaje completado",
            "mensaje": (
                "Tu viaje terminó correctamente. "
                f"Total: C$ {viaje.tarifa_final}."
            ),
            "tipo": "viaje_completado",
        },
    }

    datos_notificacion = (
        notificaciones_estado.get(
            estado_nuevo
        )
    )

    if datos_notificacion:
        programar_notificacion_viaje(
            usuario=viaje.pasajero.usuario,
            titulo=(
                datos_notificacion["titulo"]
            ),
            mensaje=(
                datos_notificacion["mensaje"]
            ),
            tipo=datos_notificacion["tipo"],
            viaje_id=viaje.id,
        )
    if estado_nuevo == "completado":
            liberar_estado_conductor(
                conductor=conductor
            )

    return viaje

@transaction.atomic
def cancelar_viaje_pasajero(
    viaje_id,
    pasajero,
    usuario,
    motivo,
):
    pasajero = (
        Pasajero.objects
        .select_for_update()
        .get(pk=pasajero.pk)
    )

    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                    "conductor",
                    "conductor__usuario",
                    "vehiculo",
                )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje no existe."
        )

    if viaje.pasajero_id != pasajero.id:
        raise ValidationError(
            "Este viaje no pertenece "
            "al pasajero autenticado."
        )

    estados_cancelables = [
        "buscando_conductor",
        "aceptado",
        "conductor_en_camino",
        "conductor_llego",
    ]

    if viaje.estado not in estados_cancelables:
        raise ValidationError(
            "El viaje ya no se puede cancelar."
        )

    estado_anterior = viaje.estado

    viaje.estado = "cancelado"
    viaje.cancelado_por = "pasajero"
    viaje.motivo_cancelacion = motivo
    viaje.fecha_cancelacion = timezone.now()

    viaje.save(
        update_fields=[
            "estado",
            "cancelado_por",
            "motivo_cancelacion",
            "fecha_cancelacion",
            "fecha_actualizacion",
        ]
    )

    (
        OfertaViaje.objects
        .filter(
            viaje=viaje,
            estado="pendiente",
        )
        .update(
            estado="cancelada",
            fecha_respuesta=timezone.now(),
        )
    )

    if viaje.vehiculo_id:
        estado_activo = (
            EstadoVehiculo.objects
            .filter(
                codigo="activo",
                activo=True,
            )
            .first()
        )

        if estado_activo:
            viaje.vehiculo.estado = (
                estado_activo
            )

            viaje.vehiculo.save(
                update_fields=[
                    "estado",
                ]
            )

    HistorialEstadoViaje.objects.create(
        viaje=viaje,
        estado_anterior=estado_anterior,
        estado_nuevo="cancelado",
        usuario=usuario,
        observacion=motivo,
    )
    if (
        viaje.conductor_id
        and viaje.conductor.usuario
    ):
        programar_notificacion_viaje(
            usuario=viaje.conductor.usuario,
            titulo="Viaje cancelado",
            mensaje=(
                "El pasajero canceló el viaje. "
                f"Motivo: {motivo}"
            ),
            tipo="viaje_cancelado_pasajero",
            viaje_id=viaje.id,
        )
    

    return viaje

@transaction.atomic
def liberar_viaje_por_conductor(
    viaje_id,
    conductor,
    usuario,
    motivo,
):
    conductor = (
        Conductor.objects
        .select_for_update()
        .get(pk=conductor.pk)
    )

    try:
        viaje = (
            Viaje.objects
            .select_for_update()
            .select_related(
                "pasajero",
                "pasajero__usuario",
                "conductor",
                "vehiculo",
            )
            .get(pk=viaje_id)
        )
    except Viaje.DoesNotExist:
        raise ValidationError(
            "El viaje no existe."
        )

    if viaje.conductor_id != conductor.id:
        raise ValidationError(
            "Este viaje no pertenece "
            "al conductor autenticado."
        )

    estados_permitidos = [
        "aceptado",
        "conductor_en_camino",
        "conductor_llego",
    ]

    if viaje.estado not in estados_permitidos:
        raise ValidationError(
            "Ya no puedes abandonar este viaje."
        )

    estado_anterior = viaje.estado
    vehiculo = viaje.vehiculo

    viaje.estado = "buscando_conductor"
    viaje.conductor = None
    viaje.vehiculo = None
    viaje.sucursal = None
    viaje.fecha_aceptacion = None
    viaje.fecha_llegada_conductor = None

    viaje.save(
        update_fields=[
            "estado",
            "conductor",
            "vehiculo",
            "sucursal",
            "fecha_aceptacion",
            "fecha_llegada_conductor",
            "fecha_actualizacion",
        ]
    )

    if vehiculo:
        estado_activo = (
            EstadoVehiculo.objects
            .filter(
                codigo="activo",
                activo=True,
            )
            .first()
        )

        if estado_activo:
            vehiculo.estado = estado_activo

            vehiculo.save(
                update_fields=[
                    "estado",
                ]
            )

    HistorialEstadoViaje.objects.create(
        viaje=viaje,
        estado_anterior=estado_anterior,
        estado_nuevo="buscando_conductor",
        usuario=usuario,
        observacion=(
            "El conductor liberó el viaje. "
            f"Motivo: {motivo}"
        ),
    )
    liberar_estado_conductor(
        conductor=conductor
    )

    programar_notificacion_viaje(
        usuario=viaje.pasajero.usuario,
        titulo="Conductor no disponible",
        mensaje=(
            "El conductor liberó la solicitud. "
            "Buscaremos otro conductor."
        ),
        tipo="conductor_libero_viaje",
        viaje_id=viaje.id,
    )

    return viaje
