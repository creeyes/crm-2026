from rest_framework import generics
from rest_framework.response import Response
from ghl_middleware.models import Propiedad, Agencia
from .serializers import PropiedadPublicaSerializer

class PublicPropertyList(generics.ListAPIView):
    serializer_class = PropiedadPublicaSerializer
    authentication_classes = [] # API Pública, sin login
    permission_classes = []

    def get_queryset(self):
        """
        Filtra las propiedades basándose en la Agencia detectada.
        Prioridad de detección:
        1. Parámetro 'agency_id' en la URL (para pruebas).
        2. Header 'Origin' (dominio desde donde pide el React).
        """
        queryset = Propiedad.objects.none()
        
        # 1. Detección por ID directo (útil para desarrollo/test)
        agency_id = self.request.query_params.get('agency_id')
        
        # 2. Detección por Dominio (Origin)
        origin = self.request.headers.get('Origin', '')
        
        target_agency = None

        if agency_id:
            # Búsqueda directa
            target_agency = Agencia.objects.filter(location_id=agency_id, active=True).first()
        elif origin:
            # Limpieza del dominio (quitamos https:// y www.)
            clean_domain = origin.replace('https://', '').replace('http://', '').replace('www.', '')
            # Buscamos la agencia que tenga este dominio (Asumiendo que añades un campo 'dominio' en el futuro)
            # Por ahora, simulamos o buscamos por nombre si coincide, o implementamos lógica custom
            # target_agency = Agencia.objects.filter(dominio__icontains=clean_domain, active=True).first()
            pass 

        # Si encontramos agencia, filtramos sus propiedades
        if target_agency:
            queryset = Propiedad.objects.filter(agencia=target_agency, estado='activo')
        
        # Opcional: Si no se encuentra agencia, devolver vacío o error.
        # Por ahora devolvemos vacío para no romper.
        
        return queryset

    def list(self, request, *args, **kwargs):
        # Sobreescribimos list para manejar casos de "Agencia no encontrada" amigablemente
        queryset = self.get_queryset()
        if not queryset.exists() and not request.query_params.get('agency_id'):
            return Response({
                "warning": "No se identificó la agencia o no tiene propiedades activas.",
                "data": []
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
