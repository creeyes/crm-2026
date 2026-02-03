from django.shortcuts import render
from rest_framework import generics
from .serializers import PropiedadPublicaSerializer

class PublicPropertyList(generics.ListAPIView):
    serializer_class = PropiedadPublicaSerializer
    authentication_classes = [] # API Pública
    permission_classes = []

    def get_queryset(self):
        # 1. Detectar quién llama (Estrategia por Dominio u Origen)
        origin = self.request.headers.get('Origin', '')
        
        # Opcional: También permitir pasar un ID manual por si hacemos pruebas
        agency_id_param = self.request.query_params.get('agency_id')

        # LÓGICA DE DETECCIÓN
        # Si tienes guardado el dominio en el modelo Agencia, haríamos:
        # agencia = Agencia.objects.filter(dominio=origin).first()
        
        # Como por ahora solo tenemos location_id, asumiremos que el Frontend
        # nos enviará su ID o mapeamos dominios aquí (hardcoded temporalmente)
        
        if agency_id_param:
            queryset = Propiedad.objects.filter(agencia__location_id=agency_id_param)
        else:
            # Si no hay ID, devolvemos vacío o error
            return Propiedad.objects.none()

        return queryset.filter(estado='activo')
