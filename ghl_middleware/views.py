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
        
        # 1. Lógica unificada para extraer location_id
        location_data = data.get('location', {})
        custom_data = data.get('customData', {}) # Extraemos customData una sola vez
        
        location_id = location_data.get('id') or custom_data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        # IMPORTANTE: Esto fallará si no has creado la Agencia en el Admin de Django con este ID
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # Extraemos IDs
        ghl_contact_id = custom_data.get('contact_id') or data.get('contact_id') or data.get('id')
        action = data.get('type', 'update')

        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'delete':
            deleted, _ = Propiedad.objects.filter(agencia=agencia, ghl_contact_id=ghl_contact_id).delete()
            return Response({'status': 'deleted', 'count': deleted})

        # Preparar datos. OJO: Usamos custom_data.get() porque GHL suele enviar estos campos ahí
        prop_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'precio': custom_data.get('precio') or data.get('precio'), # Intenta en custom, luego en root
            'zona': custom_data.get('zona') or data.get('zona'),
            'habitaciones': custom_data.get('habitaciones') or data.get('habitaciones'),
            'estado': 'activo'
        }
        
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
        
        # 1. Lógica unificada para extraer location_id
        location_data = data.get('location', {})
        custom_data = data.get('customData', {}) # Extraemos customData
        
        location_id = location_data.get('id') or custom_data.get('location_id')
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        # IMPORTANTE: Crea la agencia en el Admin si te sale error 404
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # Extraemos IDs
        ghl_contact_id = custom_data.get('contact_id') or data.get('contact_id') or data.get('id')
        
        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Preparar datos del cliente
        # CORRECCIÓN: Buscamos en custom_data primero, que es donde GHL pone los campos personalizados
        cliente_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'nombre': data.get('first_name') or data.get('full_name') or 'Unknown',
            'presupuesto_maximo': custom_data.get('presupuesto'), # Corregido: busca en customData
            'zona_interes': custom_data.get('zona_interes')       # Corregido: busca en customData
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
            
            matches_serializer = PropiedadSerializer(coincidencias, many=True)

            return Response({
                'status': 'success',
                'cliente_id': cliente.id,
                'matches_found': len(coincidencias),
                'matches': matches_serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def encontrar_coincidencias(self, cliente):
        # Nota: Asegúrate que cliente.zona_interes no sea None antes de filtrar
        if not cliente.zona_interes:
            return Propiedad.objects.none()

        return Propiedad.objects.filter(
            agencia=cliente.agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo or 999999999, # Fallback por si presupuesto es null
            estado='activo'
        )
