from django.contrib import admin
from .models import Agencia, Propiedad, Cliente

# Esto hace que aparezcan en el panel y se vean bonitos con columnas
@admin.register(Agencia)
class AgenciaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'location_id', 'api_key')
    search_fields = ('nombre', 'location_id')

@admin.register(Propiedad)
class PropiedadAdmin(admin.ModelAdmin):
    list_display = ('zona', 'precio', 'habitaciones', 'estado', 'agencia')
    list_filter = ('estado', 'zona', 'agencia')
    search_fields = ('zona', 'ghl_contact_id')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'presupuesto_maximo', 'zona_interes', 'agencia')
    list_filter = ('zona_interes', 'agencia')
    search_fields = ('nombre',)
