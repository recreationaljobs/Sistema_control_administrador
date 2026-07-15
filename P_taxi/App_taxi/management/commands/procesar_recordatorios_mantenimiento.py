import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from App_taxi.api.services import (
    construir_alerta_km_aceite,
    obtener_configuracion_sucursal,
)
from App_taxi.models import (
    TipoMantenimiento,
    Vehiculo,
)
from App_taxi.notification_services import (
    procesar_alerta_aceite_conductor,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Procesa las alertas de cambio de aceite "
        "y notifica al conductor asignado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--vehiculo",
            type=int,
            default=None,
            help=(
                "Procesa únicamente el vehículo "
                "con el ID indicado."
            ),
        )

    def handle(self, *args, **options):
        vehiculo_id = options.get("vehiculo")

        vehiculos = (
            Vehiculo.objects
            .select_related(
                "sucursal",
                "estado",
            )
            .order_by("id")
        )

        if vehiculo_id:
            vehiculos = vehiculos.filter(
                id=vehiculo_id
            )

        tipo_aceite, _ = (
            TipoMantenimiento.objects
            .get_or_create(
                codigo="aceite",
                defaults={
                    "nombre":
                        "Cambio de aceite",

                    "intervalo_km":
                        5000,
                },
            )
        )

        fecha_creacion = (
            timezone.now().isoformat()
        )

        configuraciones = {}

        vehiculos_revisados = 0
        alertas_detectadas = 0
        dispositivos_notificados = 0
        errores = 0

        for vehiculo in vehiculos:
            vehiculos_revisados += 1

            clave_sucursal = (
                vehiculo.sucursal_id
            )

            if (
                clave_sucursal
                not in configuraciones
            ):
                configuraciones[
                    clave_sucursal
                ] = (
                    obtener_configuracion_sucursal(
                        vehiculo.sucursal
                    )
                )

            configuracion = (
                configuraciones[
                    clave_sucursal
                ]
            )

            alerta = (
                construir_alerta_km_aceite(
                    vehiculo,
                    configuracion,
                    tipo_aceite,
                    fecha_creacion,
                )
            )

            if not alerta:
                continue

            alertas_detectadas += 1

            try:
                enviados = (
                    procesar_alerta_aceite_conductor(
                        vehiculo=vehiculo,
                        alerta=alerta,
                    )
                )

                dispositivos_notificados += (
                    enviados
                )

                if enviados > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            (
                                f"Vehículo "
                                f"{vehiculo.placa}: "
                                f"{enviados} "
                                f"dispositivo(s) "
                                f"notificado(s)."
                            )
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            (
                                f"Vehículo "
                                f"{vehiculo.placa}: "
                                f"alerta detectada, "
                                f"pero no se envió "
                                f"notificación."
                            )
                        )
                    )

            except Exception:
                errores += 1

                logger.exception(
                    "Error procesando la alerta "
                    "del vehículo %s.",
                    vehiculo.id,
                )

                self.stderr.write(
                    self.style.ERROR(
                        (
                            f"Error procesando "
                            f"el vehículo "
                            f"{vehiculo.placa}."
                        )
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            "Proceso de mantenimiento finalizado."
        )

        self.stdout.write(
            (
                "Vehículos revisados: "
                f"{vehiculos_revisados}"
            )
        )

        self.stdout.write(
            (
                "Alertas detectadas: "
                f"{alertas_detectadas}"
            )
        )

        self.stdout.write(
            (
                "Dispositivos notificados: "
                f"{dispositivos_notificados}"
            )
        )

        self.stdout.write(
            f"Errores: {errores}"
        )