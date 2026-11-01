from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = "Seed realistic demonstration field data for Bustard Beacon platform."

    def handle(self, *args, **options):
        self.stdout.write("Invoking Bustard Beacon realistic demo seed...")
        call_command('seed_realistic_demo')
