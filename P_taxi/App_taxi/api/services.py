from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import (
    ConfiguracionSistema,
    JornadaDiaria,
    Gasto,
    Adelanto,
    Vehiculo,
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
    kilometraje_final,
    ingreso_bruto,
    porcentaje_pago_conductor
):
    if kilometraje_final < kilometraje_inicial:
        raise ValidationError("El kilometraje final no puede ser menor al kilometraje inicial.")

    kilometros_recorridos = kilometraje_final - kilometraje_inicial

    ingreso_bruto = Decimal(ingreso_bruto or "0.00")
    porcentaje = Decimal(porcentaje_pago_conductor or "0.00")

    pago_conductor = (ingreso_bruto * porcentaje / Decimal("100")).quantize(Decimal("0.01"))

    return {
        "kilometros_recorridos": kilometros_recorridos,
        "pago_conductor": pago_conductor,
    }


def recalcular_totales_jornada(jornada):
    total_gastos = jornada.gastos.exclude(
        estado__codigo="anulado"
    ).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0.00")

    total_adelantos = jornada.adelantos.exclude(
        estado__codigo="anulado"
    ).aggregate(
        total=Sum("monto")
    )["total"] or Decimal("0.00")

    pago_pendiente = Decimal(jornada.pago_conductor) - Decimal(total_adelantos)
    saldo_excedente = Decimal("0.00")

    if pago_pendiente < 0:
        saldo_excedente = abs(pago_pendiente)
        pago_pendiente = Decimal("0.00")

    ganancia_dueno = (
        Decimal(jornada.ingreso_bruto)
        - Decimal(jornada.pago_conductor)
        - Decimal(total_gastos)
    ).quantize(Decimal("0.01"))

    JornadaDiaria.objects.filter(pk=jornada.pk).update(
        total_gastos=total_gastos,
        total_adelantos=total_adelantos,
        pago_pendiente_conductor=pago_pendiente,
        saldo_adelanto_excedente=saldo_excedente,
        ganancia_dueno=ganancia_dueno
    )

    jornada.total_gastos = total_gastos
    jornada.total_adelantos = total_adelantos
    jornada.pago_pendiente_conductor = pago_pendiente
    jornada.saldo_adelanto_excedente = saldo_excedente
    jornada.ganancia_dueno = ganancia_dueno

    return jornada


def actualizar_kilometraje_vehiculo(vehiculo, kilometraje_final):
    if kilometraje_final > vehiculo.kilometraje_actual:
        vehiculo.kilometraje_actual = kilometraje_final
        vehiculo.save(update_fields=["kilometraje_actual"])


def aplicar_mantenimiento_en_vehiculo(mantenimiento):
    vehiculo = mantenimiento.vehiculo
    tipo_codigo = mantenimiento.tipo_mantenimiento.codigo if mantenimiento.tipo_mantenimiento else None

    campos_actualizar = []

    if mantenimiento.kilometraje > vehiculo.kilometraje_actual:
        vehiculo.kilometraje_actual = mantenimiento.kilometraje
        campos_actualizar.append("kilometraje_actual")

    if tipo_codigo == "aceite":
        vehiculo.km_ultimo_cambio_aceite = mantenimiento.kilometraje
        campos_actualizar.append("km_ultimo_cambio_aceite")

        if mantenimiento.proximo_km_sugerido:
            nuevo_intervalo = mantenimiento.proximo_km_sugerido - mantenimiento.kilometraje
            vehiculo.km_intervalo_cambio_aceite = max(nuevo_intervalo, 0)
            campos_actualizar.append("km_intervalo_cambio_aceite")

    if tipo_codigo in ["preventivo", "correctivo", "reparacion"]:
        vehiculo.km_ultimo_mantenimiento = mantenimiento.kilometraje
        campos_actualizar.append("km_ultimo_mantenimiento")

        if mantenimiento.proximo_km_sugerido:
            nuevo_intervalo = mantenimiento.proximo_km_sugerido - mantenimiento.kilometraje
            vehiculo.km_intervalo_mantenimiento = max(nuevo_intervalo, 0)
            campos_actualizar.append("km_intervalo_mantenimiento")

    if campos_actualizar:
        vehiculo.save(update_fields=list(set(campos_actualizar)))


def obtener_alertas_vehiculo(vehiculo):
    alertas = []

    proximo_aceite = vehiculo.km_ultimo_cambio_aceite + vehiculo.km_intervalo_cambio_aceite
    faltan_aceite = proximo_aceite - vehiculo.kilometraje_actual

    proximo_mantenimiento = vehiculo.km_ultimo_mantenimiento + vehiculo.km_intervalo_mantenimiento
    faltan_mantenimiento = proximo_mantenimiento - vehiculo.kilometraje_actual

    if vehiculo.kilometraje_actual >= proximo_aceite:
        alertas.append({
            "vehiculo_id": vehiculo.id,
            "vehiculo": vehiculo.placa,
            "tipo": "Cambio de aceite vencido",
            "kilometraje_actual": vehiculo.kilometraje_actual,
            "proximo_km": proximo_aceite,
            "faltan_km": faltan_aceite,
            "nivel": "danger",
        })
    elif 0 <= faltan_aceite <= vehiculo.alerta_previa_km:
        alertas.append({
            "vehiculo_id": vehiculo.id,
            "vehiculo": vehiculo.placa,
            "tipo": "Cambio de aceite próximo",
            "kilometraje_actual": vehiculo.kilometraje_actual,
            "proximo_km": proximo_aceite,
            "faltan_km": faltan_aceite,
            "nivel": "warning",
        })

    if vehiculo.kilometraje_actual >= proximo_mantenimiento:
        alertas.append({
            "vehiculo_id": vehiculo.id,
            "vehiculo": vehiculo.placa,
            "tipo": "Mantenimiento vencido",
            "kilometraje_actual": vehiculo.kilometraje_actual,
            "proximo_km": proximo_mantenimiento,
            "faltan_km": faltan_mantenimiento,
            "nivel": "danger",
        })
    elif 0 <= faltan_mantenimiento <= vehiculo.alerta_previa_km:
        alertas.append({
            "vehiculo_id": vehiculo.id,
            "vehiculo": vehiculo.placa,
            "tipo": "Mantenimiento próximo",
            "kilometraje_actual": vehiculo.kilometraje_actual,
            "proximo_km": proximo_mantenimiento,
            "faltan_km": faltan_mantenimiento,
            "nivel": "warning",
        })

    return alertas


def sumar_decimal(queryset, campo):
    return queryset.aggregate(total=Sum(campo))["total"] or Decimal("0.00")


def sumar_entero(queryset, campo):
    return queryset.aggregate(total=Sum(campo))["total"] or 0