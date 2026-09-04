# Módulos de la plataforma Topo

Esta carpeta contiene las funciones nuevas para las aplicaciones móviles
Topo Driver y Topo Pasajero. El sistema administrativo actual permanece en
`App_taxi` y conserva sus rutas bajo `/api/`.

La API móvil se publica de forma independiente bajo `/api/v1/` para poder
evolucionar sin romper el panel React existente.

## Responsabilidades

- `cuentas`: activación de conductores existentes, registro móvil, códigos de
  verificación y sesiones de las aplicaciones.
- `pasajeros`: perfil del pasajero, preferencias y datos de contacto.
- `flota`: categorías taxi, mototaxi y moto; propiedad, vinculaciones con
  sucursales y habilitaciones del conductor.
- `viajes`: solicitud, asignación y ciclo de vida de los servicios.
- `tarifas`: reglas de precio y comisiones por categoría y zona.
- `seguimiento`: disponibilidad y ubicación en tiempo real.
- `common`: utilidades compartidas que no pertenecen a un dominio concreto.

## Reglas de migración

1. No mover inicialmente los modelos históricos de `App_taxi`.
2. Los modelos nuevos pueden referenciar `Usuario`, `Conductor`, `Vehiculo` y
   `Sucursal` mediante relaciones explícitas.
3. No editar migraciones aplicadas de `App_taxi`; todo cambio nuevo debe crear
   una migración posterior.
4. Los vehículos existentes recibirán la categoría `taxi` mediante una
   migración de datos separada cuando se implemente el módulo de flota.
5. Las rutas existentes `/api/` deben seguir funcionando durante toda la
   transición.
