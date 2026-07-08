from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardFinancieroView,
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
    MantenimientoViewSet,
    ConfiguracionSistemaView,
    DashboardResumenView,
    ReporteFinancieroView,
    ReporteKilometrajeView,
    AlertasMantenimientoView,
    LiquidacionView,
    LiquidacionPreviewView,
    LiquidacionReciboView,
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
router.register(r"mantenimientos", MantenimientoViewSet, basename="mantenimientos")


urlpatterns = [
    path(
        "conductores/disponibles/",
        ConductorViewSet.as_view({"get": "disponibles"}),
        name="conductores-disponibles-directo",
    ),
    path(
        "conductores/disponibles-usuario/",
        ConductorViewSet.as_view({"get": "disponibles_usuario"}),
        name="conductores-disponibles-usuario-directo",
    ),
    path(
        "conductores/<int:pk>/despedir/",
        ConductorViewSet.as_view({"post": "despedir"}),
        name="conductores-despedir-directo",
    ),
    path(
        "conductores/<int:pk>/reactivar/",
        ConductorViewSet.as_view({"post": "reactivar"}),
        name="conductores-reactivar-directo",
    ),
    path(
        "vehiculos/disponibles/",
        VehiculoViewSet.as_view({"get": "disponibles"}),
        name="vehiculos-disponibles-directo",
    ),

    path("", include(router.urls)),

    path("login/", LoginView.as_view(), name="login"),
    path("me/", MiPerfilView.as_view(), name="mi-perfil"),
    path("configuracion-sistema/", ConfiguracionSistemaView.as_view(), name="configuracion-sistema"),
    path("dashboard/resumen/", DashboardResumenView.as_view(), name="dashboard-resumen"),
    path("dashboard/financiero/", DashboardFinancieroView.as_view(), name="dashboard-financiero"),
    path("reportes/financiero/", ReporteFinancieroView.as_view(), name="reporte-financiero"),
    path("reportes/kilometraje/", ReporteKilometrajeView.as_view(), name="reporte-kilometraje"),
    path("liquidaciones/", LiquidacionView.as_view(), name="liquidaciones"),
    path("liquidaciones/preview/", LiquidacionPreviewView.as_view(), name="liquidaciones-preview"),
    path("liquidaciones/<int:pk>/recibo/", LiquidacionReciboView.as_view(), name="liquidaciones-recibo"),
    path("mantenimiento/alertas/", AlertasMantenimientoView.as_view(), name="alertas-mantenimiento"),
]