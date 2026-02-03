from rest_framework import serializers
from .models import Propiedad

class PropiedadPublicaSerializer(serializers.ModelSerializer):
    # Campos calculados para adaptarse al Frontend
    id = serializers.CharField(source='ghl_contact_id')
    title = serializers.SerializerMethodField()
    location = serializers.CharField(source='zona.nombre', default='Consultar')
    beds = serializers.IntegerField(source='habitaciones')
    baths = serializers.IntegerField(default=1) # No tienes baños en el modelo, pongo default
    sqm = serializers.IntegerField(source='metros')
    image = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=12, decimal_places=0) # Quitamos decimales para limpieza
    features = serializers.SerializerMethodField()

    class Meta:
        model = Propiedad
        fields = [
            'id', 'title', 'price', 'location', 
            'beds', 'baths', 'sqm', 'type', 
            'image', 'features', 'isFeatured'
        ]

    def get_title(self, obj):
        # Generamos un título dinámico ya que no existe en BD
        return f"Oportunidad en {obj.zona.nombre if obj.zona else 'la zona'}"

    def get_image(self, obj):
        # Tu front espera UN string, tu back tiene una lista. Devolvemos la primera.
        if obj.imagenesUrl and isinstance(obj.imagenesUrl, list) and len(obj.imagenesUrl) > 0:
            return obj.imagenesUrl[0]
        return "https://placehold.co/600x400?text=Sin+Imagen"

    def get_type(self, obj):
        return "Apartment" # Default, ya que no tienes 'tipo' en el modelo

    def get_features(self, obj):
        # Convertimos tus campos booleanos en la lista de strings que quiere el front
        features = []
        if obj.balcon == 'si': features.append('Balcón')
        if obj.garaje == 'si': features.append('Garaje')
        if obj.patioInterior == 'si': features.append('Patio Interior')
        if obj.animales == 'si': features.append('Admite Mascotas')
        return features
