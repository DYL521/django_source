from django.db import models


# Create your models here.

class Category(models.Model):
    name = models.CharField(
        max_length=100, verbose_name="名称", help_text="名称"
    )
    created_time = models.DateTimeField(auto_now_add=True)


class Book(models.Model):
    title = models.CharField(max_length=100, verbose_name="书名")
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
    udpated_time = models.DateTimeField(auto_now=True)
    crated_time = models.DateTimeField(auto_now_add=True)
