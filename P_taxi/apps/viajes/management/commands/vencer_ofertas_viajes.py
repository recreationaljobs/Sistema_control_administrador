"""Vence contraofertas que superaron su tiempo."""

from django.core.management.base import (
    BaseCommand,
)
from django.utils import timezone

from apps.viajes.models import OfertaViaje


class Command(BaseCommand):
    help = (
        "Marca como vencidas las contraofertas "
        "pendientes cuyo tiempo terminó."
    )

    def handle(self, *args, **options):
        ahora = timezone.now()

        cantidad = (
            OfertaViaje.objects
            .filter(
                estado="pendiente",
                fecha_vencimiento__lte=ahora,
            )
            .update(
                estado="vencida",
                fecha_respuesta=ahora,
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Contraofertas vencidas: "
                    f"{cantidad}"
                )
            )
        )