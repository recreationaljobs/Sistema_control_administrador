"""Crea pagos faltantes de viajes completados."""

from django.core.management.base import (
    BaseCommand,
)

from apps.viajes.models import (
    PagoViaje,
    Viaje,
)


class Command(BaseCommand):
    help = (
        "Crea pagos pendientes para viajes "
        "completados que no tienen pago."
    )

    def handle(self, *args, **options):
        viajes = (
            Viaje.objects
            .filter(
                estado="completado",
                tarifa_final__isnull=False,
                pago__isnull=True,
            )
            .only(
                "id",
                "metodo_pago",
                "tarifa_final",
            )
        )

        pagos = []

        for viaje in viajes.iterator(
            chunk_size=500
        ):
            metodo = viaje.metodo_pago

            if metodo not in {
                PagoViaje.METODO_EFECTIVO,
                PagoViaje.METODO_TARJETA,
            }:
                metodo = (
                    PagoViaje.METODO_EFECTIVO
                )

            pagos.append(
                PagoViaje(
                    viaje=viaje,
                    metodo=metodo,
                    estado=(
                        PagoViaje
                        .ESTADO_PENDIENTE
                    ),
                    moneda="NIO",
                    monto=viaje.tarifa_final,
                )
            )

        if pagos:
            PagoViaje.objects.bulk_create(
                pagos,
                batch_size=500,
                ignore_conflicts=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Pagos creados: "
                    f"{len(pagos)}"
                )
            )
        )