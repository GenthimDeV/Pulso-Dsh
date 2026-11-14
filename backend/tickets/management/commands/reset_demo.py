from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tickets import seed


class Command(BaseCommand):
    help = (
        "Restaura los datos de demostración: borra TODOS los tickets (con comentarios e "
        "historial) y las cuentas de demo, y los vuelve a crear. Las cuentas de demo se "
        "identifican por su nombre de usuario (ver tickets/seed_data.py): un usuario real con "
        "ese nombre también se borraría. No toca otros usuarios."
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
        # Una sola transacción: si el seed falla, el borrado se deshace y no queda la base vacía.
        with transaction.atomic():
            removed = seed.wipe()
            summary = seed.seed()
        self.stdout.write(
            self.style.SUCCESS(f"Restaurado ({removed['tickets']} tickets borrados): {summary}")
        )
