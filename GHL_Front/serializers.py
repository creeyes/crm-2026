from rest_framework import serializers
from ghl_middleware.models import Propiedad

class PropiedadPublicaSerializer(serializers.ModelSerializer):
    # Mapeamos los campos para que coincidan con la interfaz 'Property' de tu React
    id = serializers.CharField(source='ghl_contact_id')
    title = serializers.SerializerMethodField()
    location = serializers.CharField(source='zona.nombre', default='Consultar Ubicación')
    beds = serializers.IntegerField(source='habitaciones')
    baths = serializers.IntegerField(default=1) # Valor por defecto ya que no está en el modelo
    sqm = serializers.IntegerField(source='metros')
    image = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField() # Ej: 'Apartment', 'Villa'
    price = serializers.DecimalField(max_digits=12, decimal_places=0)
    features = serializers.SerializerMethodField()
    isFeatured = serializers.SerializerMethodField()

    class Meta:
        model = Propiedad
        fields = [
            'id', 'title', 'price', 'location', 
            'beds', 'baths', 'sqm', 'type', 
            'image', 'features', 'isFeatured'
        ]

    def get_title(self, obj):
        # Generamos un título atractivo combinando zona y municipio si existen
        zona = obj.zona.nombre if obj.zona else "Zona Exclusiva"
        municipio = obj.zona.municipio.nombre if obj.zona and obj.zona.municipio else ""
        return f"Oportunidad en {zona}, {municipio}"

    def get_image(self, obj):
        # El Front espera un string único, el Back tiene una lista en JSON
        if obj.imagenesUrl and isinstance(obj.imagenesUrl, list) and len(obj.imagenesUrl) > 0:
            return obj.imagenesUrl[0]
        # Imagen de fallback si no hay fotos
        return "https://placehold.co/600x400?text=Sin+Imagen"

    def get_type(self, obj):
        # Lógica simple para determinar tipo, puedes mejorarla con más datos
        if obj.habitaciones > 4:
            return "Villa"
        elif obj.habitaciones == 0:
            return "Studio"
        return "Apartment"

    def get_features(self, obj):
        # Convertimos tus campos 'si/no' en una lista de características
        features = []
        if obj.balcon == 'si': features.append('Balcón')
        if obj.garaje == 'si': features.append('Garaje')
        if obj.patioInterior == 'si': features.append('Patio Interior')
        if obj.animales == 'si': features.append('Admite Mascotas')
        if obj.zona: features.append(f"Zona: {obj.zona.nombre}")
        return features
        
    def get_isFeatured(self, obj):
        # Ejemplo: Destacar si el precio es alto o si tiene muchas habitaciones
        return obj.precio > 500000
