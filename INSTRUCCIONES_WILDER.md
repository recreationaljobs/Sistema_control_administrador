# Sprint `actulizacion` — instrucciones para Wilder

## Para probar esta rama localmente

1. `git fetch && git checkout actulizacion`
2. Ajusta tu `.env`: `USE_SQLITE=False` (usarás tu MySQL)
3. `python manage.py migrate`
4. `python manage.py runserver`

## Cambios principales

- Campos de licencia en Conductor (`numero_licencia`, `fecha_inicio_licencia`, `fecha_vencimiento_licencia`)
- % de comisión ahora por conductor (`Conductor.porcentaje_pago`), con fallback a config de sucursal
- Admin de sucursal no puede gestionar roles ni catálogos globales (Estados/Tipos)
- Superadmin puede dar de baja / reactivar usuarios (soft delete + revocación de tokens)
- Asignación única de vehículo (constraint + validación)
- Despedir/reactivar conductor con liberación automática de vehículo
- Alertas de kilometraje (cambio de aceite) y vencimiento de licencia
- Notificaciones celestes con animación swing y borde por severidad
- Botones huérfanos: cableados o eliminados (ver Fase G)

## PENDIENTE de conversación entre Deyvin y Wilder

- Modelo Adelanto: ¿FK a jornada (main) o independiente por conductor (rama previa)?
- Rescatar `LiquidacionConductor` de la rama `feature/deyvin-dev`
- Sacar `.env` del tracking (fuga actual en el repo)
