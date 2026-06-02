from django.db import models


class BlockedNetwork(models.Model):
    network = models.CharField(max_length=50, unique=True, verbose_name="Netzwerk/IP")
    last_seen = models.DateTimeField(verbose_name="Zuletzt gesehen")
    reason = models.CharField(max_length=255, blank=True, verbose_name="Grund")

    class Meta:
        verbose_name = "Geblockte IP/Netz"
        verbose_name_plural = "Geblockte IPs/Netze"
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.network} (zuletzt: {self.last_seen:%Y-%m-%d %H:%M})"
