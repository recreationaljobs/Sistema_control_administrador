from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from App_taxi.models import (
    Conductor,
    JornadaDiaria,
    RegistroNotificacion,
)
from App_taxi.notification_services import (
    enviar_notificacion_usuario,
)


class Command(BaseCommand):
    help = (
        "Envía recordatorios a taxistas que no han "
        "abierto o cerrado su jornada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            choices=[
                "apertura",
                "cierre",
            ],
            help=(
                "Permite probar un tipo de "
                "notificación sin esperar el horario."
            ),
        )

        parser.add_argument(
            "--usuario",
            type=int,
            help=(
                "Procesa únicamente el usuario "
                "indicado."
            ),
        )

    def handle(self, *args, **options):
        ahora = timezone.localtime()
        hoy = timezone.localdate()

        minutos_actuales = (
            ahora.hour * 60
            + ahora.minute
        )

        tipo_forzado = options.get(
            "forzar"
        )

        procesar_apertura = (
            tipo_forzado == "apertura"
            or (
                tipo_forzado is None
                and 360 <= minutos_actuales < 1200
            )
        )

        procesar_cierre = (
            tipo_forzado == "cierre"
            or (
                tipo_forzado is None
                and minutos_actuales >= 1200
            )
        )

        if (
            not procesar_apertura
            and not procesar_cierre
        ):
            self.stdout.write(
                "Todavía no corresponde enviar "
                "recordatorios."
            )
            return

        conductores = (
            Conductor.objects
            .select_related(
                "usuario",
                "usuario__rol",
            )
            .filter(
                activo=True,
                usuario__isnull=False,
                usuario__is_active=True,
                usuario__rol__codigo="taxista",
            )
        )

        usuario_id = options.get(
            "usuario"
        )

        if usuario_id:
            conductores = conductores.filter(
                usuario_id=usuario_id
            )

        enviados_total = 0

        for conductor in conductores:
            if procesar_apertura:
                enviados_total += (
                    self._procesar_apertura(
                        conductor=conductor,
                        hoy=hoy,
                    )
                )

            if procesar_cierre:
                enviados_total += (
                    self._procesar_cierre(
                        conductor=conductor,
                        hoy=hoy,
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Proceso finalizado. "
                    f"Notificaciones enviadas: "
                    f"{enviados_total}"
                )
            )
        )

    def _procesar_apertura(
        self,
        *,
        conductor,
        hoy,
    ):
        jornada_existe = (
            JornadaDiaria.objects
            .filter(
                conductor=conductor,
                fecha=hoy,
            )
            .exists()
        )

        if jornada_existe:
            return 0

        nombre = (
            f"{conductor.nombre} "
            f"{conductor.apellido}"
        ).strip()

        mensaje = (
            f"Hola {nombre}, abre tu jornada "
            "del día de hoy."
        )

        return self._registrar_y_enviar(
            usuario=conductor.usuario,
            tipo=(
                RegistroNotificacion
                .TIPO_APERTURA
            ),
            fecha_jornada=hoy,
            titulo="Recordatorio de jornada",
            mensaje=mensaje,
        )

    def _procesar_cierre(
        self,
        *,
        conductor,
        hoy,
    ):
        jornada_abierta = (
            JornadaDiaria.objects
            .filter(
                conductor=conductor,
                fecha=hoy,
                kilometraje_final__isnull=True,
            )
            .exists()
        )

        if not jornada_abierta:
            return 0

        nombre = (
            f"{conductor.nombre} "
            f"{conductor.apellido}"
        ).strip()

        mensaje = (
            f"Hola {nombre}, cierra tu jornada "
            "del día de hoy."
        )

        return self._registrar_y_enviar(
            usuario=conductor.usuario,
            tipo=(
                RegistroNotificacion
                .TIPO_CIERRE
            ),
            fecha_jornada=hoy,
            titulo="Recordatorio de jornada",
            mensaje=mensaje,
        )

    def _registrar_y_enviar(
        self,
        *,
        usuario,
        tipo,
        fecha_jornada,
        titulo,
        mensaje,
    ):
        registro, _ = (
            RegistroNotificacion.objects
            .get_or_create(
                usuario=usuario,
                tipo=tipo,
                fecha_jornada=fecha_jornada,
                defaults={
                    "titulo": titulo,
                    "mensaje": mensaje,
                },
            )
        )

        if registro.enviada:
            return 0

        registro.titulo = titulo
        registro.mensaje = mensaje
        registro.save(
            update_fields=[
                "titulo",
                "mensaje",
            ]
        )

        enviados = enviar_notificacion_usuario(
            usuario=usuario,
            titulo=titulo,
            mensaje=mensaje,
            url=settings.FRONTEND_JORNADAS_URL,
            tag=(
                f"{tipo}-"
                f"{fecha_jornada}-"
                f"{usuario.id}"
            ),
        )

        if enviados > 0:
            registro.enviada = True
            registro.fecha_envio = (
                timezone.now()
            )
            registro.save(
                update_fields=[
                    "enviada",
                    "fecha_envio",
                ]
            )

        return enviados