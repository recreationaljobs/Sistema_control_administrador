from rest_framework import permissions


def rol_codigo(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    if not getattr(user, "rol", None):
        return None

    return user.rol.codigo


def es_superadmin(user):
    return bool(
        user
        and user.is_authenticated
        and rol_codigo(user) in ["superadmin", "super_admin"]
    )


def es_admin_sucursal(user):
    return bool(
        user
        and user.is_authenticated
        and rol_codigo(user) == "admin_sucursal"
    )


def es_taxista(user):
    return bool(
        user
        and user.is_authenticated
        and rol_codigo(user) == "taxista"
    )


def es_admin_o_superadmin(user):
    return es_superadmin(user) or es_admin_sucursal(user)


class EstaAutenticado(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class EsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return es_superadmin(request.user)


class EsAdminSucursalOSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return es_admin_o_superadmin(request.user)