from rest_framework import serializers
from ghl_middleware.models import Propiedad

class PropiedadPublicaSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='ghl_contact_id')
    title = serializers.SerializerMethodField()
    
    # 1. PRECIO
    price = serializers.DecimalField(source='precio', max_digits=12, decimal_places=0)
    
    # 2. UBICACIÓN
    location = serializers.SerializerMethodField()
    
    # 3. DETALLES BÁSICOS
    beds = serializers.IntegerField(source='habitaciones')
    baths = serializers.IntegerField(default=1) # Valor por defecto si no lo tienes
    sqm = serializers.IntegerField(source='metros')
    
    # 4. IMÁGENES (Portada y Galería)
    image = serializers.SerializerMethodField() # Para la card (string)
    images = serializers.ListField(source='imagenesUrl', child=serializers.CharField(), read_only=True) # Para el detalle (array)
    
    type = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    isFeatured = serializers.SerializerMethodField()
    
    # 5. DESCRIPCIÓN (Generada automáticamente para evitar errores)
    description = serializers.SerializerMethodField()

    class Meta:
        model = Propiedad
        fields = [
            'id', 'title', 'price', 'location', 
            'beds', 'baths', 'sqm', 'type', 
            'image', 'images', 'features', 'isFeatured',
            'description' 
        ]

    # --- MÉTODOS CALCULADOS ---

    def get_title(self, obj):
        zona = obj.zona.nombre if obj.zona else "Zona Exclusiva"
        municipio = ""
        if obj.zona and obj.zona.municipio:
            municipio = obj.zona.municipio.nombre   
        if municipio:
            return f"Oportunidad en {zona}, {municipio}"
        return f"Oportunidad en {zona}"

    def get_location(self, obj):
        if obj.zona:
            return obj.zona.nombre
        return "Consultar Ubicación"

    def get_image(self, obj):
        # Devuelve la primera imagen si existe, sino un placeholder
        if obj.imagenesUrl and isinstance(obj.imagenesUrl, list) and len(obj.imagenesUrl) > 0:
            return obj.imagenesUrl[0]
        return "https://placehold.co/600x400?text=Sin+Imagen"

    def get_type(self, obj):
        if obj.habitaciones > 4: return "Villa"
        elif obj.habitaciones == 0: return "Studio"
        return "Apartment"

    def get_features(self, obj):
        features = []
        if obj.balcon == 'si': features.append('Balcón')
        if obj.garaje == 'si': features.append('Garaje')
        if obj.patioInterior == 'si': features.append('Patio Interior')
        if obj.animales == 'si': features.append('Admite Mascotas')
        if obj.zona: features.append(f"Zona: {obj.zona.nombre}")
        return features
        
    def get_isFeatured(self, obj):
        return obj.precio > 500000

    def get_description(self, obj):
        # Aquí creamos el texto "al vuelo"
        ubicacion = self.get_location(obj)
        tipo = self.get_type(obj)
        return (
            f"Excelente {tipo} situado en {ubicacion}. "
            f"Cuenta con una superficie de {obj.metros}m² y {obj.habitaciones} habitaciones. "
            "Una oportunidad única en el mercado. Contáctanos para más detalles."
        )
