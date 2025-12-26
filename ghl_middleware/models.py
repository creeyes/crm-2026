from django.db import models

class Agencia(models.Model):
    """
    Modelo Tenant que representa una agencia inmobiliaria (Subcuenta de GHL).
    """
    location_id = models.CharField(max_length=255, unique=True, primary_key=True, help_text="ID único de la subcuenta de GHL")
    api_key = models.CharField(max_length=255, help_text="Token de autorización para validar webhooks")
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.nombre} ({self.location_id})"

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
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    zona = models.CharField(max_length=255, db_index=True)
    habitaciones = models.IntegerField()
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
    nombre = models.CharField(max_length=255)
    presupuesto_maximo = models.DecimalField(max_digits=12, decimal_places=2)
    zona_interes = models.CharField(max_length=255)

    class Meta:
        unique_together = ('agencia', 'ghl_contact_id')

    def __str__(self):
        return f"Cliente {self.nombre} - {self.agencia.nombre}"
