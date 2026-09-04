"""Auditoría de integridad del sistema Topo Driver."""

from django.core.management.base import (
    BaseCommand,
)
from django.db.models import F, Q
from django.utils import timezone

from apps.seguimiento.models import (
    EstadoConductorTiempoReal,
)
from apps.viajes.models import (
    OfertaViaje,
    PagoViaje,
    Viaje,
)


class Command(BaseCommand):
    help = (
        "Revisa inconsistencias de viajes, "
        "ofertas, pagos y conductores."
    )

    def mostrar_resultado(
        self,
        nombre,
        cantidad,
    ):
        if cantidad:
            self.stdout.write(
                self.style.WARNING(
                    f"{nombre}: {cantidad}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{nombre}: 0"
                )
            )

    def handle(self, *args, **options):
        ahora = timezone.now()

        estados_con_conductor = [
            "aceptado",
            "conductor_en_camino",
            "conductor_llego",
            "en_curso",
            "completado",
        ]

        viajes_sin_conductor = (
            Viaje.objects
            .filter(
                estado__in=(
                    estados_con_conductor
                ),
                conductor__isnull=True,
            )
            .count()
        )

        viajes_sin_vehiculo = (
            Viaje.objects
            .filter(
                estado__in=(
                    estados_con_conductor
                ),
                vehiculo__isnull=True,
            )
            .count()
        )

        completados_sin_tarifa = (
            Viaje.objects
            .filter(
                estado="completado",
                tarifa_final__isnull=True,
            )
            .count()
        )

        completados_sin_pago = (
            Viaje.objects
            .filter(
                estado="completado",
                tarifa_final__isnull=False,
                pago__isnull=True,
            )
            .count()
        )

        pagos_monto_incorrecto = (
            PagoViaje.objects
            .filter(
                viaje__tarifa_final__isnull=False,
            )
            .exclude(
                monto=F(
                    "viaje__tarifa_final"
                )
            )
            .count()
        )

        ofertas_vencidas_pendientes = (
            OfertaViaje.objects
            .filter(
                estado="pendiente",
                fecha_vencimiento__lte=ahora,
            )
            .count()
        )

        ofertas_en_viajes_cerrados = (
            OfertaViaje.objects
            .filter(
                estado="pendiente",
            )
            .exclude(
                viaje__estado=(
                    "buscando_conductor"
                )
            )
            .count()
        )

        conductores_disponibles_con_viaje = (
            EstadoConductorTiempoReal.objects
            .filter(
                disponible=True,
                viaje_actual__isnull=False,
            )
            .count()
        )

        conductores_ocupados_sin_viaje = (
            EstadoConductorTiempoReal.objects
            .filter(
                disponible=False,
                en_linea=True,
                viaje_actual__isnull=True,
            )
            .filter(
                Q(conductor__activo=True)
            )
            .count()
        )

        self.stdout.write(
            "\nAuditoría Topo Driver\n"
        )

        self.mostrar_resultado(
            "Viajes sin conductor",
            viajes_sin_conductor,
        )

        self.mostrar_resultado(
            "Viajes sin vehículo",
            viajes_sin_vehiculo,
        )

        self.mostrar_resultado(
            "Completados sin tarifa final",
            completados_sin_tarifa,
        )

        self.mostrar_resultado(
            "Completados sin pago",
            completados_sin_pago,
        )

        self.mostrar_resultado(
            "Pagos con monto diferente",
            pagos_monto_incorrecto,
        )

        self.mostrar_resultado(
            "Ofertas vencidas pendientes",
            ofertas_vencidas_pendientes,
        )

        self.mostrar_resultado(
            "Ofertas pendientes en viajes cerrados",
            ofertas_en_viajes_cerrados,
        )

        self.mostrar_resultado(
            "Conductores disponibles con viaje",
            conductores_disponibles_con_viaje,
        )

        self.mostrar_resultado(
            "Conductores ocupados sin viaje",
            conductores_ocupados_sin_viaje,
        )

        total_problemas = sum([
            viajes_sin_conductor,
            viajes_sin_vehiculo,
            completados_sin_tarifa,
            completados_sin_pago,
            pagos_monto_incorrecto,
            ofertas_vencidas_pendientes,
            ofertas_en_viajes_cerrados,
            conductores_disponibles_con_viaje,
            conductores_ocupados_sin_viaje,
        ])

        self.stdout.write("")

        if total_problemas:
            self.stdout.write(
                self.style.WARNING(
                    (
                        "Total de posibles "
                        "inconsistencias: "
                        f"{total_problemas}"
                    )
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "No se encontraron inconsistencias."
                )
            )