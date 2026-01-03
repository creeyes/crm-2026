from django.db import models

# --- 1. MODELO DE INFRAESTRUCTURA (CRUZADO / OAUTH) ---

class GHLToken(models.Model):
    """
    Guarda los tokens de acceso generados por el Marketplace de GHL.
    Es vital para validar que la App está instalada legalmente y para refrescar tokens.
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
    api_key = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Token de autorización (Opcional si usas OAuth)"
    )
    nombre = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=True, help_text="Desactiva la agencia si deja de pagar")

    def __str__(self):
        return f"{self.nombre or 'Agencia Sin Nombre'} ({self.location_id})"


class Propiedad(models.Model):
    """
    Representa el Custom Object 'Propiedad' de GHL.
    """
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('vendido', 'Vendido'),
    ]

    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name='propiedades')
    ghl_contact_id = models.CharField(max_length=255, help_text="ID del REGISTRO (Record ID) del Custom Object en GHL")
    
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    zona = models.CharField(max_length=255, db_index=True, blank=True, null=True)
    habitaciones = models.IntegerField(default=0, help_text="Nº de habitaciones que tiene la propiedad")
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='activo')

    class Meta:
        unique_together = ('agencia', 'ghl_contact_id')
        indexes = [
            models.Index(fields=['zona', 'precio', 'habitaciones']), # Indexado para búsquedas rápidas
        ]

    def __str__(self):
        return f"Propiedad {self.ghl_contact_id} - {self.zona} ({self.habitaciones} habs)"


class Cliente(models.Model):
    """
    Representa el Contacto (Buyer Lead) de GHL.
    """
    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name='clientes')
    ghl_contact_id = models.CharField(max_length=255, help_text="ID del CONTACTO en GHL")
    
    nombre = models.CharField(max_length=255, blank=True, default="Desconocido")
    presupuesto_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    zona_interes = models.CharField(max_length=255, blank=True, null=True)
    
    # NUEVO CAMPO SOLICITADO:
    habitaciones_minimas = models.IntegerField(default=0, help_text="Nº mínimo de habitaciones que busca el cliente")

    created_at = models.DateTimeField(auto_now_add=True)

    # NUEVO CAMPO DE RELACIÓN (Many-to-Many):
    # Esto permite guardar qué propiedades se han emparejado con este cliente.
    # 'blank=True' permite crear clientes sin propiedades asignadas.
    propiedades_interes = models.ManyToManyField(
        Propiedad, 
        related_name='interesados', 
        blank=True,
        help_text="Historial de propiedades que hacen match con este cliente"
    )

    class Meta:
        unique_together = ('agencia', 'ghl_contact_id')

    def __str__(self):
        return f"Cliente {self.nombre} - Busca {self.habitaciones_minimas} habs en {self.zona_interes}"
