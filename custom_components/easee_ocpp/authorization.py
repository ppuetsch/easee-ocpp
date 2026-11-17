"""Which RFID cards may charge: the tags registered in Home Assistant (Settings → Tags).

The integration keeps no card list of its own. A card is accepted if a tag with its id
exists; accepted cards are reported as tag scans (event tag_scanned, last scanned time).
Unknown cards are rejected and not registered - registering them would allow them the
next time. Every decision fires easee_ocpp_authorization, so automations can react
(e.g. notify about an unknown card). With "accept all cards" every card is accepted and
registered as tag.
"""

from __future__ import annotations

from homeassistant.components.tag import TAG_DATA, async_scan_tag
from homeassistant.core import HomeAssistant, callback

from .const import EVENT_AUTHORIZATION
from .models import IdTag, Serial

# RemoteStartTransaction from Home Assistant uses this tag; it is always accepted.
REMOTE_START_ID_TAG = "HOMEASSISTANT"


def normalised_id_tag(id_tag: IdTag) -> str:
    """Compare card ids case-insensitively and without surrounding blanks."""
    return id_tag.strip().upper()


class TagAuthorizer:
    """Answers the charger's Authorize and StartTransaction requests from the HA tags."""

    def __init__(self, hass: HomeAssistant, accept_all_cards: bool) -> None:
        """Decide based on the tag registry, or accept everything."""
        self._hass = hass
        self._accept_all_cards = accept_all_cards

    def registered_tag_id(self, id_tag: IdTag) -> str | None:
        """Return the id of the HA tag matching the card, or None if there is none."""
        wanted = normalised_id_tag(id_tag)
        tags = self._hass.data[TAG_DATA].data
        return next((tag_id for tag_id in tags if normalised_id_tag(tag_id) == wanted), None)

    @callback
    def is_allowed(self, serial: Serial, id_tag: IdTag) -> bool:
        """Decide, report accepted cards as tag scans and fire the authorization event."""
        if normalised_id_tag(id_tag) == REMOTE_START_ID_TAG:
            return True
        tag_id = self.registered_tag_id(id_tag)
        allowed = tag_id is not None or self._accept_all_cards
        if allowed:
            self._hass.async_create_task(async_scan_tag(self._hass, tag_id or id_tag, None))
        self._hass.bus.async_fire(EVENT_AUTHORIZATION, {"serial": serial, "id_tag": id_tag, "accepted": allowed})
        return allowed
