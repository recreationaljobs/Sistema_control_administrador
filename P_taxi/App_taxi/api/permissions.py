from rest_framework import permissions


def rol_codigo(user):
    if not user or not user.is_authenticated:
        return None

    if not getattr(user, "rol", None):
        return None

    return user.rol.codigo


def es_superadmin(user):
    return user.is_authenticated and rol_codigo(user) == "superadmin"


def es_admin_sucursal(user):
    return user.is_authenticated and rol_codigo(user) == "admin_sucursal"


def es_taxista(user):
    return user.is_authenticated and rol_codigo(user) == "taxista"


def es_admin_o_superadmin(user):
    return es_superadmin(user) or es_admin_sucursal(user)


class EsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return es_superadmin(request.user)


class EsAdminSucursalOSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return es_admin_o_superadmin(request.user)


class EstaAutenticado(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated