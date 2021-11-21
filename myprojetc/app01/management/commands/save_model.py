# -*- coding: utf-8 -*-
from django.core.management import BaseCommand
from app01.models import Category, Book


class Command(BaseCommand):

    def handle(self, *args, **options):
        category = Category.objects.create(
            name="计算机科学"
        )
        book = Book()
        book.title = "计算机导论"
        book.category = category
        book.save()
