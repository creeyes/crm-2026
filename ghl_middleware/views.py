from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Agencia, Propiedad, Cliente
from .serializers import PropiedadSerializer, ClienteSerializer

class WebhookPropiedadView(APIView):
    """
    Endpoint para Crear/Actualizar/Borrar Propiedades desde GHL.
    """
    def post(self, request):
        data = request.data
        location_id = data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        ghl_contact_id = data.get('contact_id') or data.get('id')
        action = data.get('type', 'update')

        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'delete':
            deleted, _ = Propiedad.objects.filter(agencia=agencia, ghl_contact_id=ghl_contact_id).delete()
            return Response({'status': 'deleted', 'count': deleted})

        # Preparar datos para el serializer
        prop_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'precio': data.get('precio'),
            'zona': data.get('zona'),
            'habitaciones': data.get('habitaciones'),
            'estado': 'activo'
        }
        
        # Intentar obtener instancia existente para update
        try:
            propiedad = Propiedad.objects.get(agencia=agencia, ghl_contact_id=ghl_contact_id)
            serializer = PropiedadSerializer(propiedad, data=prop_data)
        except Propiedad.DoesNotExist:
            serializer = PropiedadSerializer(data=prop_data)

        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WebhookClienteView(APIView):
    """
    Endpoint para Crear/Actualizar Clientes y disparar Matching.
    """
    def post(self, request):
        data = request.data
        
        # 1. Intentamos leer del objeto estándar 'location' de GHL
        location_data = data.get('location', {})
        location_id = location_data.get('id')
    
        # Fallback: Si no está ahí, buscamos donde lo tenías tú (customData)
        if not location_id:
            custom_data = data.get('customData', {})
            location_id = custom_data.get('location_id')
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        ghl_contact_id = data.get('contact_id') or data.get('id')
        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        cliente_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'nombre': data.get('first_name', 'Unknown'),
            'presupuesto_maximo': data.get('presupuesto'),
            'zona_interes': data.get('zona_interes')
        }

        try:
            cliente = Cliente.objects.get(agencia=agencia, ghl_contact_id=ghl_contact_id)
            serializer = ClienteSerializer(cliente, data=cliente_data)
        except Cliente.DoesNotExist:
            serializer = ClienteSerializer(data=cliente_data)

        if serializer.is_valid():
            cliente = serializer.save()
            
            # Disparar lógica de Matching
            coincidencias = self.encontrar_coincidencias(cliente)
            
            # Serializar resultados
            matches_serializer = PropiedadSerializer(coincidencias, many=True)

            return Response({
                'status': 'success',
                'cliente_id': cliente.id,
                'matches_found': len(coincidencias),
                'matches': matches_serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def encontrar_coincidencias(self, cliente):
        """
        Lógica de Matching protegida por ORM.
        """
        return Propiedad.objects.filter(
            agencia=cliente.agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            estado='activo'
        )
