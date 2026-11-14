from django.core.management.base import BaseCommand, CommandError

from tickets import seed


class Command(BaseCommand):
    help = (
        "Restaura los datos de demostración: borra TODOS los tickets (con comentarios e "
        "historial) y las cuentas de demo, y los vuelve a crear. No toca otros usuarios."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="No pedir confirmación.")

    def handle(self, *args, **options):
        if not options["yes"]:
            try:
                answer = input("Se borrarán los tickets y las cuentas de demo. ¿Seguir? [s/N] ")
            except EOFError:
                raise CommandError("Sin terminal interactiva: usa --yes.") from None
            if answer.strip().lower() not in {"s", "si", "sí", "y", "yes"}:
                self.stdout.write("Cancelado.")
                return
        removed = seed.wipe()
        summary = seed.seed()
        self.stdout.write(
            self.style.SUCCESS(f"Restaurado ({removed['tickets']} tickets borrados): {summary}")
        )
