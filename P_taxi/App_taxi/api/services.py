from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError


from ..models import (
    ConfiguracionSistema,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Vehiculo,
    Mantenimiento,
    EstadoAdelanto,
    Liquidacion,
    DetalleLiquidacion,
)

def obtener_configuracion_sucursal(sucursal):
    config, _ = ConfiguracionSistema.objects.get_or_create(sucursal=sucursal)
    return config


def obtener_rango_periodo(periodo):
    hoy = timezone.localdate()

    if periodo == "dia":
        return hoy, hoy

    if periodo == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio, hoy

    if periodo == "mes":
        inicio = hoy.replace(day=1)
        return inicio, hoy

    if periodo == "anio":
        inicio = hoy.replace(month=1, day=1)
        return inicio, hoy

    raise ValidationError("Período inválido. Usa: dia, semana, mes o anio.")


def calcular_campos_jornada(
    kilometraje_inicial,
    kilometraje_final=None,
    ingreso_bruto="0.00",
    porcentaje_pago_conductor="0.00",
    tipo_cobro="porcentaje",
    monto_alquiler="0.00",
):
    ingreso_bruto = Decimal(ingreso_bruto or "0.00")
    porcentaje = Decimal(porcentaje_pago_conductor or "0.00")
    monto_alquiler = Decimal(monto_alquiler or "0.00")

    if kilometraje_final is None:
        kilometros_recorridos = 0
    else:
        if kilometraje_final < kilometraje_inicial:
            raise ValidationError(
                "El kilometraje final no puede ser menor al kilometraje inicial."
            )

        kilometros_recorridos = kilometraje_final - kilometraje_inicial

    if tipo_cobro == "alquiler":
        return {
            "kilometros_recorridos": kilometros_recorridos,
            "pago_conductor": Decimal("0.00"),
            "ingreso_bruto": monto_alquiler,
        }

    pago_conductor = (
        ingreso_bruto * porcentaje / Decimal("100")
    ).quantize(Decimal("0.01"))

    return {
        "kilometros_recorridos": kilometros_recorridos,
        "pago_conductor": pago_conductor,
        "ingreso_bruto": ingreso_bruto,
    }


def recalcular_totales_jornada(jornada):
    total_adelantos = jornada.adelantos.filter(
        Q(estado__codigo__iexact="adelanto") |
        Q(estado__codigo__iexact="anticipo")
    ).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0.00")

    tipo_cobro = getattr(jornada, "tipo_cobro", "porcentaje")

    if tipo_cobro == "alquiler":
        ingreso_bruto = Decimal(jornada.monto_alquiler or "0.00")
        pago_conductor = Decimal("0.00")
        pago_pendiente = Decimal("0.00")
        saldo_excedente = Decimal("0.00")
        ganancia_dueno = ingreso_bruto.quantize(Decimal("0.01"))

    else:
        ingreso_bruto = Decimal(jornada.ingreso_bruto or "0.00")
        pago_conductor = Decimal(jornada.pago_conductor or "0.00")

        pago_pendiente = pago_conductor - Decimal(total_adelantos)
        saldo_excedente = Decimal("0.00")

        if pago_pendiente < 0:
            saldo_excedente = abs(pago_pendiente)
            pago_pendiente = Decimal("0.00")

        ganancia_dueno = (
            ingreso_bruto - pago_conductor
        ).quantize(Decimal("0.01"))

    JornadaDiaria.objects.filter(pk=jornada.pk).update(
        ingreso_bruto=ingreso_bruto,
        pago_conductor=pago_conductor,
        total_gastos=Decimal("0.00"),
        total_adelantos=total_adelantos,
        pago_pendiente_conductor=pago_pendiente,
        saldo_adelanto_excedente=saldo_excedente,
        ganancia_dueno=ganancia_dueno,
    )

    jornada.ingreso_bruto = ingreso_bruto
    jornada.pago_conductor = pago_conductor
    jornada.total_gastos = Decimal("0.00")
    jornada.total_adelantos = total_adelantos
    jornada.pago_pendiente_conductor = pago_pendiente
    jornada.saldo_adelanto_excedente = saldo_excedente
    jornada.ganancia_dueno = ganancia_dueno

    return jornada


def actualizar_kilometraje_vehiculo(vehiculo, kilometraje_final):
    if kilometraje_final is None:
        return

    if kilometraje_final > vehiculo.kilometraje_actual:
        vehiculo.kilometraje_actual = kilometraje_final
        vehiculo.save(update_fields=["kilometraje_actual"])

CODIGOS_TIPO_ACEITE = {
    "aceite",
    "cambio_aceite",
}

CODIGOS_TIPO_MANTENIMIENTO = {
    "mantenimiento",
    "preventivo",
    "correctivo",
    "reparacion",
}

CODIGOS_ESTADO_FINALIZADO = {
    "finalizado",
    "finalizada",
    "completado",
    "completa",
}


def _codigo_normalizado(valor):
    return str(valor or "").strip().lower()


def _q_estados_finalizados():
    consulta = Q()

    for codigo in CODIGOS_ESTADO_FINALIZADO:
        consulta |= Q(
            estado__codigo__iexact=codigo
        )

    return consulta


def filtrar_mantenimientos_finalizados(queryset):
    return queryset.filter(
        _q_estados_finalizados()
    )


def mantenimiento_esta_finalizado(mantenimiento):
    codigo_estado = _codigo_normalizado(
        getattr(
            getattr(
                mantenimiento,
                "estado",
                None,
            ),
            "codigo",
            "",
        )
    )

    return (
        codigo_estado
        in CODIGOS_ESTADO_FINALIZADO
    )


def _obtener_mantenimientos_vehiculo(vehiculo):
    precargados = getattr(
        vehiculo,
        "mantenimientos_dashboard_prefetch",
        None,
    )

    if precargados is not None:
        return list(precargados)

    return list(
        vehiculo.mantenimientos
        .select_related(
            "tipo_mantenimiento",
            "estado",
        )
        .order_by(
            "-kilometraje",
            "-fecha",
            "-id",
        )
    )


def _ultimo_mantenimiento_finalizado(
    mantenimientos,
    codigos_tipo,
):
    candidatos = []

    for mantenimiento in mantenimientos:
        if not mantenimiento_esta_finalizado(
            mantenimiento
        ):
            continue

        codigo_tipo = _codigo_normalizado(
            getattr(
                getattr(
                    mantenimiento,
                    "tipo_mantenimiento",
                    None,
                ),
                "codigo",
                "",
            )
        )

        if codigo_tipo in codigos_tipo:
            candidatos.append(mantenimiento)

    if not candidatos:
        return None

    return max(
        candidatos,
        key=lambda item: (
            int(item.kilometraje or 0),
            item.fecha,
            item.id,
        ),
    )


def _tiene_registros_tipo(
    mantenimientos,
    codigos_tipo,
):
    for mantenimiento in mantenimientos:
        codigo_tipo = _codigo_normalizado(
            getattr(
                getattr(
                    mantenimiento,
                    "tipo_mantenimiento",
                    None,
                ),
                "codigo",
                "",
            )
        )

        if codigo_tipo in codigos_tipo:
            return True

    return False


def _calcular_estado_servicio(
    *,
    nombre,
    codigo,
    vehiculo,
    ultimo,
    kilometraje_fallback,
    intervalo,
    aviso_previo,
):
    km_actual = int(
        vehiculo.kilometraje_actual or 0
    )

    intervalo = max(
        int(intervalo or 0),
        1,
    )

    aviso_previo = max(
        int(aviso_previo or 0),
        0,
    )

    if ultimo:
        kilometraje_base = int(
            ultimo.kilometraje or 0
        )
        fuente = "historial"
        registro_id = ultimo.id
    else:
        kilometraje_base = int(
            kilometraje_fallback or 0
        )
        fuente = (
            "vehiculo"
            if kilometraje_base > 0
            else "sin_historial"
        )
        registro_id = None

    if kilometraje_base <= 0:
        return {
            "codigo": codigo,
            "nombre": nombre,
            "estado": "sin_historial",
            "nivel": "info",
            "kilometraje_actual": km_actual,
            "kilometraje_base": None,
            "proximo_km": None,
            "faltan_km": None,
            "km_excedidos": 0,
            "intervalo_km": intervalo,
            "aviso_previo_km": aviso_previo,
            "ultimo_registro_id": registro_id,
            "fuente": fuente,
        }

    proximo_km = (
        kilometraje_base
        + intervalo
    )

    faltan_km = (
        proximo_km
        - km_actual
    )

    if faltan_km <= 0:
        estado = "vencido"
        nivel = "danger"
    elif faltan_km <= aviso_previo:
        estado = "proximo"
        nivel = "warning"
    else:
        estado = "bueno"
        nivel = "success"

    return {
        "codigo": codigo,
        "nombre": nombre,
        "estado": estado,
        "nivel": nivel,
        "kilometraje_actual": km_actual,
        "kilometraje_base": kilometraje_base,
        "proximo_km": proximo_km,
        "faltan_km": faltan_km,
        "km_excedidos": (
            abs(faltan_km)
            if faltan_km < 0
            else 0
        ),
        "intervalo_km": intervalo,
        "aviso_previo_km": aviso_previo,
        "ultimo_registro_id": registro_id,
        "fuente": fuente,
    }


def _construir_alerta_servicio(
    vehiculo,
    servicio,
):
    estado = servicio["estado"]

    if estado not in {
        "proximo",
        "vencido",
    }:
        return None

    es_vencido = (
        estado == "vencido"
    )

    if es_vencido:
        titulo = (
            f"{servicio['nombre']} vencido"
        )

        mensaje = (
            f"El vehículo {vehiculo.placa} "
            f"tiene el servicio vencido por "
            f"{servicio['km_excedidos']} km."
        )
    else:
        titulo = (
            f"{servicio['nombre']} próximo"
        )

        mensaje = (
            f"Al vehículo {vehiculo.placa} "
            f"le faltan {servicio['faltan_km']} km "
            f"para el servicio."
        )

    return {
        "id": (
            f"{servicio['codigo']}-"
            f"{vehiculo.id}-"
            f"{servicio['proximo_km']}"
        ),
        "vehiculo_id": vehiculo.id,
        "vehiculo": vehiculo.placa,
        "tipo_codigo": servicio["codigo"],
        "tipo": titulo,
        "mensaje": mensaje,
        "kilometraje_actual": (
            servicio["kilometraje_actual"]
        ),
        "proximo_km": servicio["proximo_km"],
        "faltan_km": servicio["faltan_km"],
        "km_excedidos": (
            servicio["km_excedidos"]
        ),
        "nivel": servicio["nivel"],
        "severidad": (
            "critical"
            if es_vencido
            else "warning"
        ),
        "link": "/mantenimiento",
    }


def obtener_estado_mantenimiento_vehiculo(
    vehiculo,
    configuracion=None,
):
    configuracion = (
        configuracion
        or obtener_configuracion_sucursal(
            vehiculo.sucursal
        )
    )

    mantenimientos = (
        _obtener_mantenimientos_vehiculo(
            vehiculo
        )
    )

    ultimo_aceite = (
        _ultimo_mantenimiento_finalizado(
            mantenimientos,
            CODIGOS_TIPO_ACEITE,
        )
    )

    ultimo_general = (
        _ultimo_mantenimiento_finalizado(
            mantenimientos,
            CODIGOS_TIPO_MANTENIMIENTO,
        )
    )

    tiene_registros_aceite = (
        _tiene_registros_tipo(
            mantenimientos,
            CODIGOS_TIPO_ACEITE,
        )
    )

    tiene_registros_generales = (
        _tiene_registros_tipo(
            mantenimientos,
            CODIGOS_TIPO_MANTENIMIENTO,
        )
    )

    aceite = _calcular_estado_servicio(
        nombre="Cambio de aceite",
        codigo="aceite",
        vehiculo=vehiculo,
        ultimo=ultimo_aceite,
        kilometraje_fallback=(
            0
            if tiene_registros_aceite
            else vehiculo.km_ultimo_cambio_aceite
        ),
        intervalo=(
            configuracion
            .intervalo_cambio_aceite_km
        ),
        aviso_previo=(
            configuracion
            .km_aviso_mantenimiento
        ),
    )

    mantenimiento = (
        _calcular_estado_servicio(
            nombre="Mantenimiento",
            codigo="mantenimiento",
            vehiculo=vehiculo,
            ultimo=ultimo_general,
            kilometraje_fallback=(
                0
                if tiene_registros_generales
                else vehiculo.km_ultimo_mantenimiento
            ),
            intervalo=(
                configuracion
                .intervalo_mantenimiento_km
            ),
            aviso_previo=(
                configuracion
                .alerta_previa_km
            ),
        )
    )

    estados = {
        aceite["estado"],
        mantenimiento["estado"],
    }

    if "vencido" in estados:
        estado_general = "vencido"
    elif "proximo" in estados:
        estado_general = "proximo"
    elif "sin_historial" in estados:
        estado_general = "sin_historial"
    else:
        estado_general = "bueno"

    alertas = []

    for servicio in [
        aceite,
        mantenimiento,
    ]:
        alerta = _construir_alerta_servicio(
            vehiculo,
            servicio,
        )

        if alerta:
            alertas.append(alerta)

    return {
        "vehiculo_id": vehiculo.id,
        "vehiculo": vehiculo.placa,
        "estado_general": estado_general,
        "aceite": aceite,
        "mantenimiento": mantenimiento,
        "alertas": alertas,
    }


def sincronizar_mantenimiento_vehiculo(
    vehiculo,
):
    configuracion = (
        obtener_configuracion_sucursal(
            vehiculo.sucursal
        )
    )

    mantenimientos = list(
        vehiculo.mantenimientos
        .select_related(
            "tipo_mantenimiento",
            "estado",
        )
        .order_by(
            "-kilometraje",
            "-fecha",
            "-id",
        )
    )

    ultimo_aceite = (
        _ultimo_mantenimiento_finalizado(
            mantenimientos,
            CODIGOS_TIPO_ACEITE,
        )
    )

    ultimo_general = (
        _ultimo_mantenimiento_finalizado(
            mantenimientos,
            CODIGOS_TIPO_MANTENIMIENTO,
        )
    )

    tiene_registros_aceite = (
        _tiene_registros_tipo(
            mantenimientos,
            CODIGOS_TIPO_ACEITE,
        )
    )

    tiene_registros_generales = (
        _tiene_registros_tipo(
            mantenimientos,
            CODIGOS_TIPO_MANTENIMIENTO,
        )
    )

    if ultimo_aceite:
        vehiculo.km_ultimo_cambio_aceite = int(
            ultimo_aceite.kilometraje
        )
    elif tiene_registros_aceite:
        vehiculo.km_ultimo_cambio_aceite = 0

    if ultimo_general:
        vehiculo.km_ultimo_mantenimiento = int(
            ultimo_general.kilometraje
        )
    elif tiene_registros_generales:
        vehiculo.km_ultimo_mantenimiento = 0

    vehiculo.km_intervalo_cambio_aceite = (
        int(
            configuracion
            .intervalo_cambio_aceite_km
            or 5000
        )
    )

    vehiculo.km_intervalo_mantenimiento = (
        int(
            configuracion
            .intervalo_mantenimiento_km
            or 10000
        )
    )

    vehiculo.alerta_previa_km = int(
        configuracion.alerta_previa_km
        or 0
    )

    vehiculo.save(
        update_fields=[
            "km_ultimo_cambio_aceite",
            "km_ultimo_mantenimiento",
            "km_intervalo_cambio_aceite",
            "km_intervalo_mantenimiento",
            "alerta_previa_km",
        ]
    )

    return vehiculo


def aplicar_mantenimiento_en_vehiculo(
    mantenimiento,
):
    vehiculo = mantenimiento.vehiculo

    if (
        mantenimiento_esta_finalizado(
            mantenimiento
        )
        and int(
            mantenimiento.kilometraje or 0
        )
        > int(
            vehiculo.kilometraje_actual or 0
        )
    ):
        vehiculo.kilometraje_actual = int(
            mantenimiento.kilometraje
        )

        vehiculo.save(
            update_fields=[
                "kilometraje_actual",
            ]
        )

    return sincronizar_mantenimiento_vehiculo(
        vehiculo
    )


def obtener_alertas_vehiculo(
    vehiculo,
    configuracion=None,
):
    estado = (
        obtener_estado_mantenimiento_vehiculo(
            vehiculo,
            configuracion,
        )
    )

    return estado["alertas"]


def construir_alerta_km_aceite(
    vehiculo,
    config,
    tipo_aceite,
    fecha_creacion,
):
    estado = (
        obtener_estado_mantenimiento_vehiculo(
            vehiculo,
            config,
        )
    )

    alerta = next(
        (
            item
            for item in estado["alertas"]
            if item["tipo_codigo"] == "aceite"
        ),
        None,
    )

    if not alerta:
        return None

    resultado = dict(alerta)
    resultado["fecha_creacion"] = (
        fecha_creacion
    )
    resultado["id"] = (
        f"mantenimiento_km-{vehiculo.id}-"
        f"{resultado['proximo_km']}"
    )

    return resultado

def construir_alerta_licencia(conductor, hoy, fecha_creacion):
    """Alerta de vencimiento de licencia por conductor activo. Severidad según
    días restantes: <=7 o vencida -> critical, 8-15 -> warning, 16-30 -> info."""
    venc = conductor.fecha_vencimiento_licencia
    if not venc:
        return None

    dias = (venc - hoy).days
    nombre = f"{conductor.nombre} {conductor.apellido}".strip()

    if dias < 0:
        severidad = "critical"
        mensaje = f"Licencia de {nombre} vencida hace {abs(dias)} días."
    elif dias <= 7:
        severidad = "critical"
        mensaje = f"La licencia de {nombre} vence en {dias} días."
    elif dias <= 15:
        severidad = "warning"
        mensaje = f"La licencia de {nombre} vence en {dias} días."
    elif dias <= 30:
        severidad = "info"
        mensaje = f"La licencia de {nombre} vence en {dias} días."
    else:
        return None

    return {
        "id": f"licencia_vencimiento-{conductor.id}",
        "tipo": "licencia_vencimiento",
        "severidad": severidad,
        "mensaje": mensaje,
        "fecha_creacion": fecha_creacion,
        "link": f"/conductores/{conductor.id}",
        "conductor_id": conductor.id,
        "conductor": nombre,
        "fecha_vencimiento": str(venc),
        "dias_restantes": dias,
    }


def sumar_decimal(queryset, campo):
    return queryset.aggregate(total=Sum(campo))["total"] or Decimal("0.00")


def sumar_entero(queryset, campo):
    return queryset.aggregate(total=Sum(campo))["total"] or 0

@transaction.atomic
def procesar_liquidacion_manual(
    *,
    liquidacion,
    usuario,
):
    """
    Procesa desde Django Admin una liquidación ya creada.

    Las jornadas que ya tienen un DetalleLiquidacion
    no vuelven a calcularse.
    """

    liquidacion = (
        Liquidacion.objects
        .select_for_update()
        .select_related(
            "conductor",
            "sucursal",
        )
        .get(pk=liquidacion.pk)
    )

    if liquidacion.detalles.exists():
        return {
            "procesada": False,
            "mensaje": (
                "Esta liquidación ya fue procesada. "
                "No se calcularon nuevamente sus jornadas."
            ),
        }

    conductor = liquidacion.conductor
    fecha_inicio = liquidacion.fecha_inicio
    fecha_fin = liquidacion.fecha_fin

    if not conductor:
        return {
            "procesada": False,
            "mensaje": "Debes seleccionar un conductor.",
        }

    if not fecha_inicio or not fecha_fin:
        return {
            "procesada": False,
            "mensaje": (
                "Debes indicar la fecha de inicio "
                "y la fecha final."
            ),
        }

    if fecha_inicio > fecha_fin:
        return {
            "procesada": False,
            "mensaje": (
                "La fecha de inicio no puede ser "
                "posterior a la fecha final."
            ),
        }

    misma_fecha_ya_liquidada = (
        Liquidacion.objects
        .filter(
            conductor=conductor,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            detalles__isnull=False,
        )
        .exclude(pk=liquidacion.pk)
        .exists()
    )

    if misma_fecha_ya_liquidada:
        return {
            "procesada": False,
            "mensaje": (
                "Este conductor ya tiene una liquidación "
                "procesada para el mismo rango de fechas."
            ),
        }

    jornadas = (
        JornadaDiaria.objects
        .select_for_update()
        .select_related(
            "conductor",
            "vehiculo",
            "sucursal",
        )
        .filter(
            conductor=conductor,
            fecha__range=(
                fecha_inicio,
                fecha_fin,
            ),
            kilometraje_final__isnull=False,
            pago_pendiente_conductor__gt=Decimal("0.00"),
            detalles_liquidacion__isnull=True,
        )
    )

    if conductor.sucursal_id is None:
        jornadas = jornadas.filter(
            sucursal__isnull=True
        )
    else:
        jornadas = jornadas.filter(
            sucursal_id=conductor.sucursal_id
        )

    jornadas = list(
        jornadas
        .distinct()
        .order_by(
            "fecha",
            "id",
        )
    )

    if not jornadas:
        return {
            "procesada": False,
            "mensaje": (
                "No existen jornadas pendientes dentro "
                "del rango seleccionado. Es posible que "
                "esas fechas ya hayan sido liquidadas."
            ),
        }

    total_jornadas = sum(
        (
            Decimal(
                jornada.pago_conductor
                or "0.00"
            )
            for jornada in jornadas
        ),
        Decimal("0.00"),
    )

    movimientos = (
        Adelanto.objects
        .select_related("estado")
        .filter(conductor=conductor)
    )

    if conductor.sucursal_id is None:
        movimientos = movimientos.filter(
            sucursal__isnull=True
        )
    else:
        movimientos = movimientos.filter(
            sucursal_id=conductor.sucursal_id
        )

    total_adelantos = Decimal("0.00")
    total_abonos = Decimal("0.00")

    for movimiento in movimientos:
        codigo = str(
            movimiento.estado.codigo
            if movimiento.estado
            else ""
        ).strip().lower()

        monto = Decimal(
            movimiento.monto
            or "0.00"
        )

        if codigo in {
            "abono",
            "abonado",
        }:
            total_abonos += monto
        else:
            total_adelantos += monto

    pendiente_adelantos = (
        total_adelantos
        - total_abonos
    )

    if pendiente_adelantos < Decimal("0.00"):
        pendiente_adelantos = Decimal("0.00")

    abono_aplicado = Decimal(
        liquidacion.abono_aplicado
        or "0.00"
    )

    ajuste_manual = Decimal(
        liquidacion.ajuste_manual
        or "0.00"
    )

    if abono_aplicado < Decimal("0.00"):
        return {
            "procesada": False,
            "mensaje": (
                "El abono aplicado no puede ser negativo."
            ),
        }

    if ajuste_manual < Decimal("0.00"):
        return {
            "procesada": False,
            "mensaje": (
                "El ajuste manual no puede ser negativo."
            ),
        }

    if abono_aplicado > pendiente_adelantos:
        return {
            "procesada": False,
            "mensaje": (
                "El abono aplicado no puede ser mayor "
                "que el saldo pendiente de adelantos."
            ),
        }

    total_pago = (
        total_jornadas
        - abono_aplicado
        + ajuste_manual
    )

    if total_pago < Decimal("0.00"):
        total_pago = Decimal("0.00")

    detalles = [
        DetalleLiquidacion(
            liquidacion=liquidacion,
            jornada=jornada,
            fecha=jornada.fecha,
            vehiculo=(
                str(jornada.vehiculo)
                if jornada.vehiculo
                else ""
            ),
            kilometros_recorridos=(
                jornada.kilometros_recorridos
                or 0
            ),
            ingreso_bruto=(
                jornada.ingreso_bruto
                or Decimal("0.00")
            ),
            pago_conductor=(
                jornada.pago_conductor
                or Decimal("0.00")
            ),
        )
        for jornada in jornadas
    ]

    DetalleLiquidacion.objects.bulk_create(
        detalles
    )

    ids_jornadas = [
        jornada.id
        for jornada in jornadas
    ]

    JornadaDiaria.objects.filter(
        id__in=ids_jornadas
    ).update(
        pago_pendiente_conductor=Decimal("0.00"),
        saldo_adelanto_excedente=Decimal("0.00"),
    )

    liquidacion.sucursal = conductor.sucursal
    liquidacion.usuario = usuario
    liquidacion.jornadas_count = len(jornadas)
    liquidacion.total_jornadas = total_jornadas
    liquidacion.total_adelantos_pendientes = (
        pendiente_adelantos
    )
    liquidacion.total_pago = total_pago

    liquidacion.save(
        update_fields=[
            "sucursal",
            "usuario",
            "jornadas_count",
            "total_jornadas",
            "total_adelantos_pendientes",
            "total_pago",
        ]
    )

    if abono_aplicado > Decimal("0.00"):
        estado_abono, _ = (
            EstadoAdelanto.objects
            .get_or_create(
                codigo="abono",
                defaults={
                    "nombre": "Abono",
                    "activo": True,
                },
            )
        )

        Adelanto.objects.create(
            sucursal=conductor.sucursal,
            conductor=conductor,
            estado=estado_abono,
            monto=abono_aplicado,
            fecha=liquidacion.fecha,
            observacion=(
                "Abono aplicado en liquidación "
                f"#{liquidacion.id}"
            ),
        )

    return {
        "procesada": True,
        "mensaje": (
            f"Liquidación #{liquidacion.id} procesada "
            f"correctamente con {len(jornadas)} jornada(s)."
        ),
    }