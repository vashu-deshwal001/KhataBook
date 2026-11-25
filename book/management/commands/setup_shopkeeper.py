from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from book.models import User


class Command(BaseCommand):
    help = 'Create the initial shopkeeper account without sample data.'

    def handle(self, *args, **options):
        if User.objects.exists():
            raise CommandError('Accounts already exist. No accounts or passwords were changed.')
        password = getpass('Choose a shopkeeper password: ')
        confirmation = getpass('Confirm password: ')
        if not password or password != confirmation:
            raise CommandError('Passwords must be non-empty and match. No account was created.')
        User.objects.create_superuser('shopkeeper', password=password, role='admin', first_name='Shopkeeper')
        self.stdout.write(self.style.SUCCESS('Shopkeeper created. Username: shopkeeper'))
