from django.contrib import admin
from .models import Atelier

# Register your models here.
@admin.register(Atelier)
class AtelierAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)
    list_filter = ("nom",)
