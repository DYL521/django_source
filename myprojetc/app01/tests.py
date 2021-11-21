from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import TestCase

# Create your tests here.
from app01.models import Category, Book
from django.utils.six import StringIO





class tets__aa(TestCase):
    def call_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "save_model",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_dry_run(self):
        self.call_command()
