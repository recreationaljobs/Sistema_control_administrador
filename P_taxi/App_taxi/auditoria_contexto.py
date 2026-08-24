from threading import local


_contexto = local()


def establecer_request(request):
    _contexto.request = request


def obtener_request():
    return getattr(_contexto, "request", None)


def limpiar_request():
    if hasattr(_contexto, "request"):
        del _contexto.request