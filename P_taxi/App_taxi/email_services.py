from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def enviar_correo_usuario_creado(
    *,
    usuario,
    password_plano,
):
    """
    Envía las credenciales al correo registrado.

    Retorna True si el correo fue enviado.
    Retorna False si el usuario no tiene correo.
    """

    correo_destino = (
        usuario.email or ""
    ).strip()

    if not correo_destino:
        return False

    nombre_completo = (
        f"{usuario.first_name or ''} "
        f"{usuario.last_name or ''}"
    ).strip()

    if not nombre_completo:
        nombre_completo = usuario.username

    rol_nombre = (
        usuario.rol.nombre
        if usuario.rol
        else "Sin rol"
    )

    sucursal_nombre = (
        usuario.sucursal.nombre
        if usuario.sucursal
        else "Sin sucursal"
    )

    login_url = getattr(
        settings,
        "SISTEMA_LOGIN_URL",
        "https://taxiadmin.servitaxitortuguero.com/login",
    )

    asunto = (
        "Tu cuenta fue registrada "
        "en el Sistema de Taxis"
    )

    mensaje_texto = f"""
Hola, {nombre_completo}.

Tu cuenta ha sido registrada exitosamente en el Sistema de Administración de Taxis.

Puedes acceder mediante el siguiente enlace:
{login_url}

Credenciales de acceso:

Usuario: {usuario.username}
Contraseña: {password_plano}
Rol: {rol_nombre}
Sucursal: {sucursal_nombre}

Por seguridad, no compartas tus credenciales con otras personas.

Este es un mensaje automático.
""".strip()

    mensaje_html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
</head>

<body
    style="
        margin: 0;
        padding: 0;
        background-color: #f1f5f9;
        font-family: Arial, Helvetica, sans-serif;
        color: #0f172a;
    "
>
    <table
        width="100%"
        cellpadding="0"
        cellspacing="0"
        role="presentation"
        style="background-color: #f1f5f9;"
    >
        <tr>
            <td
                align="center"
                style="padding: 30px 15px;"
            >
                <table
                    width="100%"
                    cellpadding="0"
                    cellspacing="0"
                    role="presentation"
                    style="
                        max-width: 620px;
                        background-color: #ffffff;
                        border-radius: 18px;
                        overflow: hidden;
                        border: 1px solid #e2e8f0;
                    "
                >
                    <tr>
                        <td
                            style="
                                background-color: #f5b800;
                                padding: 25px 30px;
                                text-align: center;
                            "
                        >
                            <h1
                                style="
                                    margin: 0;
                                    font-size: 24px;
                                    color: #ffffff;
                                "
                            >
                                Sistema de Administración de Taxis
                            </h1>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 30px;">
                            <h2
                                style="
                                    margin-top: 0;
                                    color: #0f172a;
                                    font-size: 21px;
                                "
                            >
                                Hola, {nombre_completo}
                            </h2>

                            <p
                                style="
                                    font-size: 15px;
                                    line-height: 1.6;
                                    color: #475569;
                                "
                            >
                                Tu cuenta ha sido registrada
                                exitosamente en el sistema.
                            </p>

                            <div
                                style="
                                    margin: 25px 0;
                                    padding: 20px;
                                    border-radius: 14px;
                                    background-color: #f8fafc;
                                    border: 1px solid #e2e8f0;
                                "
                            >
                                <p
                                    style="
                                        margin: 0 0 12px 0;
                                        font-size: 14px;
                                    "
                                >
                                    <strong>Usuario:</strong>
                                    {usuario.username}
                                </p>

                                <p
                                    style="
                                        margin: 0 0 12px 0;
                                        font-size: 14px;
                                    "
                                >
                                    <strong>Contraseña:</strong>
                                    {password_plano}
                                </p>

                                <p
                                    style="
                                        margin: 0 0 12px 0;
                                        font-size: 14px;
                                    "
                                >
                                    <strong>Rol:</strong>
                                    {rol_nombre}
                                </p>

                                <p
                                    style="
                                        margin: 0;
                                        font-size: 14px;
                                    "
                                >
                                    <strong>Sucursal:</strong>
                                    {sucursal_nombre}
                                </p>
                            </div>

                            <div
                                style="
                                    text-align: center;
                                    margin: 28px 0;
                                "
                            >
                                <a
                                    href="{login_url}"
                                    style="
                                        display: inline-block;
                                        padding: 13px 24px;
                                        border-radius: 12px;
                                        background-color: #f5b800;
                                        color: #ffffff;
                                        font-weight: bold;
                                        text-decoration: none;
                                    "
                                >
                                    Ingresar al sistema
                                </a>
                            </div>

                            <p
                                style="
                                    font-size: 13px;
                                    line-height: 1.6;
                                    color: #64748b;
                                "
                            >
                                Por seguridad, no compartas tus
                                credenciales con otras personas.
                            </p>

                            <p
                                style="
                                    margin-bottom: 0;
                                    font-size: 12px;
                                    color: #94a3b8;
                                "
                            >
                                Este es un mensaje automático.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
""".strip()

    correo = EmailMultiAlternatives(
        subject=asunto,
        body=mensaje_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[correo_destino],
    )

    correo.attach_alternative(
        mensaje_html,
        "text/html",
    )

    enviados = correo.send(
        fail_silently=False
    )

    return enviados == 1