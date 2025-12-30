from django.db import models

# --- 1. MODELO DE INFRAESTRUCTURA (CRUZADO / OAUTH) ---
class GHLToken(models.Model):
    """
    Guarda los tokens de acceso generados por el Marketplace de GHL.
    Es vital para validar que la App está instalada legalmente.
    """
    location_id = models.CharField(max_length=255, primary_key=True, help_text="ID de la subcuenta que instaló la app")
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_type = models.CharField(max_length=50)
    expires_in = models.IntegerField(default=86400)
    scope = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Token GHL - {self.location_id}"


# --- 2. MODELOS DE NEGOCIO (INMOBILIARIA) ---

class Agencia(models.Model):
    """
    Modelo Tenant que representa una agencia inmobiliaria (Subcuenta de GHL).
    """
    location_id = models.CharField(
        max_length=255, 
        unique=True, 
        primary_key=True, 
        help_text="ID único de la subcuenta de GHL"
    )
    # Hacemos estos campos opcionales para que la instalación automática (OAuth) no falle
    api_key = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Token de autorización para validar webhooks (Opcional si usas OAuth)"
    )
    nombre = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True, help_text="Desactiva la agencia si deja de pagar")

    def __str__(self):
        return f"{self.nombre or 'Agencia Sin Nombre'} ({self.location_id})"

class Propiedad(models.Model):
    """
    Modelo que representa una propiedad inmobiliaria.
    """
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('vendido', 'Vendido'),
    ]

    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name='propiedades')
    ghl_contact_id = models.CharField(max_length=255, help_text="ID del contacto/producto en GHL")
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    zona = models.CharField(max_length=255, db_index=True, blank=True, null=True)
    habitaciones = models.IntegerField(default=0)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='activo')

    class Meta:
        unique_together = ('agencia', 'ghl_contact_id')
        indexes = [
            models.Index(fields=['zona', 'precio']),
        ]

    def __str__(self):
        return f"Propiedad {self.ghl_contact_id} - {self.zona}"

class Cliente(models.Model):
    """
    Modelo que representa un comprador potencial.
    """
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name='clientes')
    ghl_contact_id = models.CharField(max_length=255, help_text="ID del contacto en GHL")
    nombre = models.CharField(max_length=255, blank=True, default="Desconocido")
    presupuesto_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    zona_interes = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('agencia', 'ghl_contact_id')

    def __str__(self):
        return f"Cliente {self.nombre} - {self.agencia.location_id}"
