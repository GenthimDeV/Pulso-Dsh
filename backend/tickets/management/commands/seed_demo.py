from django.core.management.base import BaseCommand

from tickets import seed


class Command(BaseCommand):
    help = (
        "Crea los datos de demostración (cuentas, tickets, comentarios e historial) con semilla "
        "fija. Si ya hay datos no hace nada; para restaurarlos usa reset_demo."
    )

    def handle(self, *args, **options):
        if seed.is_seeded():
            self.stdout.write("Ya hay datos; no se cambia nada. Para restaurar: reset_demo --yes.")
            return
        summary = seed.seed()
        self.stdout.write(self.style.SUCCESS(f"Datos de demostración creados: {summary}"))
        self.stdout.write(
            f"Cuentas de demo: {seed.data.DEMO_AGENT_USERNAME} y "
            f"{seed.data.DEMO_REQUESTER_USERNAME} (contraseña: DEMO_PASSWORD o la de por defecto)."
        )
