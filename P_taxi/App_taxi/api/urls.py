from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LoginView,
    MiPerfilView,
    SucursalViewSet,
    RolViewSet,
    UsuarioViewSet,
    EstadoVehiculoViewSet,
    EstadoJornadaViewSet,
    TipoGastoViewSet,
    EstadoGastoViewSet,
    EstadoAdelantoViewSet,
    TipoMantenimientoViewSet,
    EstadoMantenimientoViewSet,
    ConductorViewSet,
    VehiculoViewSet,
    AsignacionVehiculoViewSet,
    JornadaDiariaViewSet,
    GastoViewSet,
    AdelantoViewSet,
    LiquidacionConductorViewSet,
    MantenimientoViewSet,
    ConfiguracionSistemaView,
    DashboardResumenView,
    ReporteFinancieroView,
    ReporteKilometrajeView,
    AlertasMantenimientoView,
)

router = DefaultRouter()

router.register(r"sucursales", SucursalViewSet, basename="sucursales")
router.register(r"roles", RolViewSet, basename="roles")
router.register(r"usuarios", UsuarioViewSet, basename="usuarios")

router.register(r"estados-vehiculo", EstadoVehiculoViewSet, basename="estados-vehiculo")
router.register(r"estados-jornada", EstadoJornadaViewSet, basename="estados-jornada")
router.register(r"tipos-gasto", TipoGastoViewSet, basename="tipos-gasto")
router.register(r"estados-gasto", EstadoGastoViewSet, basename="estados-gasto")
router.register(r"estados-adelanto", EstadoAdelantoViewSet, basename="estados-adelanto")
router.register(r"tipos-mantenimiento", TipoMantenimientoViewSet, basename="tipos-mantenimiento")
router.register(r"estados-mantenimiento", EstadoMantenimientoViewSet, basename="estados-mantenimiento")

router.register(r"conductores", ConductorViewSet, basename="conductores")
router.register(r"vehiculos", VehiculoViewSet, basename="vehiculos")
router.register(r"asignaciones", AsignacionVehiculoViewSet, basename="asignaciones")
router.register(r"jornadas", JornadaDiariaViewSet, basename="jornadas")
router.register(r"gastos", GastoViewSet, basename="gastos")
router.register(r"adelantos", AdelantoViewSet, basename="adelantos")
router.register(r"liquidaciones", LiquidacionConductorViewSet, basename="liquidaciones")
router.register(r"mantenimientos", MantenimientoViewSet, basename="mantenimientos")

urlpatterns = [
    path("", include(router.urls)),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MiPerfilView.as_view(), name="mi-perfil"),
    path("configuracion/", ConfiguracionSistemaView.as_view(), name="configuracion-sistema"),
    path("dashboard/resumen/", DashboardResumenView.as_view(), name="dashboard-resumen"),
    path("reportes/financiero/", ReporteFinancieroView.as_view(), name="reporte-financiero"),
    path("reportes/kilometraje/", ReporteKilometrajeView.as_view(), name="reporte-kilometraje"),
    path("mantenimiento/alertas/", AlertasMantenimientoView.as_view(), name="alertas-mantenimiento"),
]