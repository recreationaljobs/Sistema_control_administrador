"""Desconecta conductores que dejaron de enviar actividad."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.seguimiento.models import (
    EstadoConductorTiempoReal,
)


TIEMPO_EXPIRACION_SEGUNDOS = 90


class Command(BaseCommand):
    help = (
        "Marca como desconectados a los conductores "
        "que no han enviado actividad recientemente."
    )

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(
            seconds=TIEMPO_EXPIRACION_SEGUNDOS
        )

        estados_inactivos = (
            EstadoConductorTiempoReal.objects
            .filter(
                en_linea=True,
                ultima_conexion__lt=limite,
            )
        )

        cantidad = estados_inactivos.update(
            en_linea=False,
            disponible=False,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Conductores desconectados: {cantidad}"
            )
        )