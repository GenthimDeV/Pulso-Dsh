"""Datos inventados para el seed de demostración. Nada de esto es real."""

DEMO_AGENT_USERNAME = "agente"
DEMO_REQUESTER_USERNAME = "solicitante"

# (username, nombre, apellidos, equipo). El primero es la cuenta de demo y el despachador.
AGENTS = [
    (DEMO_AGENT_USERNAME, "Lucía", "Mora", "Soporte de puesto"),
    ("marco.vidal", "Marco", "Vidal", "Redes e infraestructura"),
    ("irene.soler", "Irene", "Soler", "Cuentas y accesos"),
    ("tomas.leon", "Tomás", "León", "Aplicaciones y ERP"),
]

# El primero es la cuenta de demo (y el que más tickets abre, para que su vista no quede vacía).
REQUESTERS = [
    (DEMO_REQUESTER_USERNAME, "Carla", "Núñez"),
    ("diego.ramos", "Diego", "Ramos"),
    ("paula.ibarra", "Paula", "Ibarra"),
    ("ivan.castro", "Iván", "Castro"),
    ("marta.pons", "Marta", "Pons"),
    ("hugo.vera", "Hugo", "Vera"),
    ("elena.sanz", "Elena", "Sanz"),
    ("raul.mena", "Raúl", "Mena"),
]

# Agente que suele llevar cada categoría (por equipo).
CATEGORY_TEAM = {
    "Redes": "Redes e infraestructura",
    "Hardware": "Soporte de puesto",
    "Correo": "Soporte de puesto",
    "Cuentas": "Cuentas y accesos",
    "Accesos": "Cuentas y accesos",
    "Aplicaciones": "Aplicaciones y ERP",
    "ERP": "Aplicaciones y ERP",
}

PLACES = ["Sede Norte", "Sede Sur", "Planta 2", "Almacén", "Recepción", "Oficina remota", "Taller"]

# (categoría, asunto, descripción)
TICKET_TEMPLATES = [
    (
        "Redes",
        "Sin conexión a la VPN",
        "Desde esta mañana la VPN corporativa no llega a conectar y da tiempo de espera agotado.",
    ),
    (
        "Redes",
        "Wi-Fi muy lento en la sala de reuniones",
        "Las videollamadas se cortan cada pocos minutos; en el resto de la oficina va bien.",
    ),
    (
        "Redes",
        "No se puede acceder a la carpeta compartida",
        "La unidad de red de Administración no aparece en el explorador de archivos.",
    ),
    (
        "Redes",
        "Corte de internet intermitente",
        "Se pierde la conexión unos segundos varias veces por hora, sobre todo por la tarde.",
    ),
    (
        "Hardware",
        "El portátil no enciende",
        "Tras dejarlo cargando toda la noche no responde al botón de encendido.",
    ),
    (
        "Hardware",
        "Pantalla con líneas verticales",
        "Aparecen líneas de colores en el monitor secundario y a veces se apaga.",
    ),
    (
        "Hardware",
        "La impresora atasca el papel",
        "La impresora de la planta se queda con el papel a medias y marca un error de bandeja.",
    ),
    (
        "Hardware",
        "Teclado con varias teclas sin respuesta",
        "Las teclas de la fila superior fallan; ya se probó con otro puerto USB.",
    ),
    (
        "Correo",
        "No llegan los correos de clientes",
        "Hace dos días que no recibo mensajes de dominios externos, solo los internos.",
    ),
    (
        "Correo",
        "Buzón lleno",
        "Outlook avisa de que el buzón supera el límite y no deja enviar mensajes.",
    ),
    (
        "Correo",
        "Falta la firma corporativa",
        "Tras el cambio de equipo la firma automática ya no aparece en los correos nuevos.",
    ),
    (
        "Correo",
        "Correos legítimos marcados como spam",
        "Los avisos de un proveedor acaban siempre en la carpeta de correo no deseado.",
    ),
    (
        "Cuentas",
        "Restablecer contraseña",
        "He olvidado la contraseña y el enlace de recuperación no me llega.",
    ),
    (
        "Cuentas",
        "Cuenta bloqueada tras varios intentos",
        "El sistema indica que mi cuenta está bloqueada desde el inicio de la jornada.",
    ),
    (
        "Cuentas",
        "Alta de una persona nueva",
        "Se incorpora un compañero el lunes y necesita usuario, correo y equipo preparados.",
    ),
    (
        "Cuentas",
        "Cambio de nombre en la cuenta",
        "Mi apellido aparece mal escrito en el directorio y en el correo.",
    ),
    (
        "Accesos",
        "Sin permiso en la carpeta de Contabilidad",
        "Necesito acceso de lectura a los informes de cierre de mes.",
    ),
    (
        "Accesos",
        "Tarjeta de acceso al edificio no funciona",
        "El lector de la puerta principal rechaza mi tarjeta desde ayer.",
    ),
    (
        "Accesos",
        "Acceso a la herramienta de proyectos",
        "Piden que me añadan al espacio del equipo nuevo para poder ver las tareas.",
    ),
    (
        "Accesos",
        "Doble factor en el móvil nuevo",
        "He cambiado de teléfono y el código de verificación ya no se genera.",
    ),
    (
        "Aplicaciones",
        "El CRM se cierra al abrir una ficha",
        "Al abrir la ficha de ciertos clientes la aplicación se cierra sin mensaje.",
    ),
    (
        "Aplicaciones",
        "Instalar el programa de diseño",
        "Necesito la última versión del programa de maquetación para un encargo.",
    ),
    (
        "Aplicaciones",
        "La hoja de cálculo compartida va muy lenta",
        "El archivo de seguimiento tarda más de un minuto en abrirse y se bloquea al editar.",
    ),
    (
        "Aplicaciones",
        "Error al exportar informes a PDF",
        "La exportación termina con un error genérico y genera un archivo vacío.",
    ),
    (
        "ERP",
        "No se generan las facturas del mes",
        "El proceso de facturación termina sin errores pero no crea ningún documento.",
    ),
    (
        "ERP",
        "Stock desactualizado en el almacén",
        "Las existencias que muestra el ERP no coinciden con el último inventario.",
    ),
    (
        "ERP",
        "Error al registrar un pedido",
        "Al guardar el pedido aparece 'cliente no válido' aunque el cliente existe.",
    ),
    (
        "ERP",
        "Informe de ventas con datos duplicados",
        "El informe semanal cuenta dos veces algunos pedidos de la misma fecha.",
    ),
]

REQUESTER_COMMENTS = [
    "Sigue pasando, ¿hay novedades?",
    "He probado lo que me indicaste y no ha cambiado nada.",
    "Gracias, ya funciona. Os aviso si vuelve a fallar.",
    "Es bastante urgente, tengo una entrega hoy.",
    "Adjunto el mensaje exacto que me aparece por pantalla.",
    "Puedo estar localizable toda la tarde por si necesitáis revisarlo en persona.",
]

AGENT_COMMENTS = [
    "Hola, ya estoy revisando tu caso. Te cuento en cuanto tenga novedades.",
    "¿Puedes reiniciar el equipo y decirme si el problema continúa?",
    "He reproducido el fallo y estoy preparando la corrección.",
    "Hecho el cambio. Prueba de nuevo y confírmame si todo va bien.",
    "Necesito algo más de información: ¿desde cuándo ocurre exactamente?",
    "Lo he escalado con el proveedor; te aviso apenas respondan.",
    "Pasaré por tu puesto después de comer para verlo contigo.",
    "Queda resuelto por nuestra parte. Si reaparece, responde aquí y lo reabrimos.",
]

INTERNAL_NOTES = [
    "Parece el mismo problema que vimos con otro usuario la semana pasada.",
    "Pendiente de confirmar con el proveedor antes de tocar nada en producción.",
    "Solución temporal aplicada; falta revisar la causa de fondo.",
    "El usuario no tiene permisos suficientes; consultar con su responsable.",
    "Cambio hecho fuera de horario para no afectar al resto del equipo.",
    "Revisar de nuevo mañana a primera hora.",
]
