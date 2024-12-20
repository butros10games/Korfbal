"""This module contains the Club model."""

from django.db import models
from django.urls import reverse
from uuidv7 import uuid7


class Club(models.Model):
    """Model for a club."""

    id_uuid = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=255, unique=True)
    admin = models.ManyToManyField(
        "player.Player", through="ClubAdmin", related_name="clubs", blank=True
    )
    logo = models.ImageField(
        upload_to="club_pictures/",
        default="/static/images/clubs/blank-club-picture.png",
        blank=True,
    )

    def __str__(self) -> str:
        """Return the name of the club."""
        return str(self.name)

    def get_absolute_url(self) -> str:
        """Return the absolute url of the club."""
        return reverse("club_detail", kwargs={"club_id": self.id_uuid})

    def get_club_logo(self) -> str:
        """Return the club logo."""
        if "static" in self.logo.url:
            return self.logo.url
        else:
            return "/media" + self.logo.url
