"""Single source of the English and German texts of the Easee Local OCPP integration.

Merges them into strings.json, translations/en.json and translations/de.json, so the
three files never drift apart. Run after changing a text:

    python scripts/ocpp_translations.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

type Texts = dict[str, Any]

INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "easee_ocpp"

STATUS_STATES_EN = {
    "available": "Available",
    "preparing": "Preparing",
    "charging": "Charging",
    "suspendedevse": "Suspended by charger",
    "suspendedev": "Suspended by vehicle",
    "finishing": "Finishing",
    "reserved": "Reserved",
    "unavailable": "Unavailable",
    "faulted": "Faulted",
}
STATUS_STATES_DE = {
    "available": "Verfügbar",
    "preparing": "Vorbereitung",
    "charging": "Lädt",
    "suspendedevse": "Pausiert durch Charger",
    "suspendedev": "Pausiert durch Fahrzeug",
    "finishing": "Beendet",
    "reserved": "Reserviert",
    "unavailable": "Nicht verfügbar",
    "faulted": "Fehler",
}


def without_ocpp_prefix(name: str) -> str:
    """The device is already called '<charger> OCPP'; entity names drop the prefix."""
    bare = name.removeprefix("OCPP ").removeprefix("OCPP-")
    return bare[:1].upper() + bare[1:]


def entity_names(names: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Turn {platform: {key: name}} into the translation structure with ocpp_ prefix."""
    return {
        platform: {key: {"name": without_ocpp_prefix(name)} for key, name in keys.items()}
        for platform, keys in names.items()
    }


ENTITY_NAMES_EN = {
    "sensor": {
        "status": "OCPP status",
        "power": "OCPP power",
        "energy": "OCPP energy meter",
        "session_energy": "OCPP session energy",
        "session_start": "OCPP session start",
        "current_offered": "OCPP current offered",
        "charging_limit": "OCPP charging limit",
        "temperature": "OCPP temperature",
        "current_l1": "OCPP current L1",
        "current_l2": "OCPP current L2",
        "current_l3": "OCPP current L3",
        "voltage_l1": "OCPP voltage L1",
        "voltage_l2": "OCPP voltage L2",
        "voltage_l3": "OCPP voltage L3",
        "last_rfid_card": "OCPP last RFID card",
        "error_code": "OCPP error code",
        "vendor_error_code": "OCPP vendor error code",
        "transaction_id": "OCPP transaction id",
        "last_message": "OCPP last message",
        "meter_value_interval": "OCPP meter value interval",
        "firmware": "OCPP firmware",
    },
    "binary_sensor": {
        "connected": "OCPP connected",
        "transaction": "OCPP session active",
        "charging": "OCPP charging",
    },
    "number": {"max_current": "OCPP max current"},
    "switch": {"available": "OCPP available", "charge": "OCPP charge"},
    "button": {
        "soft_reset": "OCPP restart",
        "hard_reset": "OCPP reboot",
        "unlock": "OCPP unlock cable",
        "refresh": "OCPP refresh",
    },
}
ENTITY_NAMES_DE = {
    "sensor": {
        "status": "OCPP-Status",
        "power": "OCPP-Leistung",
        "energy": "OCPP-Zählerstand",
        "session_energy": "OCPP-Energie Ladevorgang",
        "session_start": "OCPP-Beginn Ladevorgang",
        "current_offered": "OCPP-angebotener Strom",
        "charging_limit": "OCPP-Ladelimit",
        "temperature": "OCPP-Temperatur",
        "current_l1": "OCPP-Strom L1",
        "current_l2": "OCPP-Strom L2",
        "current_l3": "OCPP-Strom L3",
        "voltage_l1": "OCPP-Spannung L1",
        "voltage_l2": "OCPP-Spannung L2",
        "voltage_l3": "OCPP-Spannung L3",
        "last_rfid_card": "OCPP-letzte RFID-Karte",
        "error_code": "OCPP-Fehlercode",
        "vendor_error_code": "OCPP-Herstellerfehlercode",
        "transaction_id": "OCPP-Transaktions-ID",
        "last_message": "OCPP-letzte Nachricht",
        "meter_value_interval": "OCPP-Messintervall",
        "firmware": "OCPP-Firmware",
    },
    "binary_sensor": {
        "connected": "OCPP verbunden",
        "transaction": "OCPP-Ladevorgang aktiv",
        "charging": "OCPP lädt",
    },
    "number": {"max_current": "OCPP-Maximalstrom"},
    "switch": {"available": "OCPP verfügbar", "charge": "OCPP laden"},
    "button": {
        "soft_reset": "OCPP-Neustart",
        "hard_reset": "OCPP-Hardware-Neustart",
        "unlock": "OCPP Kabel entriegeln",
        "refresh": "OCPP aktualisieren",
    },
}

SUBENTRY_EN: Texts = {
    "entry_type": "OCPP charger",
    "initiate_flow": {
        "user": "Connect charger via local OCPP",
        "reconfigure": "Change OCPP address",
    },
    "step": {
        "user": {
            "title": "Connect charger via local OCPP",
            "description": (
                "The charger will connect directly to Home Assistant (OCPP 1.6). "
                "The Easee cloud keeps working in parallel. Select the charger:"
            ),
            "data": {"serial": "Charger"},
        },
        "prerequisites": {
            "title": "Check requirements – {charger}",
            "description": (
                "{firmware_check} Firmware {firmware} (344 or newer required)\n"
                "{wifi_check} Connected via Wi-Fi (over cellular the charger cannot reach Home Assistant)\n"
                "{operator_check} Operator of the site: {operator} (must be Easee; change it in the Easee app if not)\n"
                "{circuit_check} No dynamic circuit limit below the fuse rating\n\n"
                "Important: while OCPP is active the charger only starts charging after Home Assistant "
                "accepted the RFID card. Register your cards as tags (Settings → Tags, tag ID = card ID); "
                "the sensor 'Last RFID card' shows the ID of a card held to the charger."
            ),
            "data": {"reset_circuit_limit": "Lift the dynamic circuit limit to the fuse rating"},
            "data_description": {
                "reset_circuit_limit": "Otherwise the circuit limit from the cloud keeps capping the OCPP limits."
            },
        },
        "address": {
            "title": "Address of Home Assistant – {charger}",
            "description": (
                "The charger connects to this address and appends /{serial}. It must be reachable from the "
                "charger's network: use the IP address or a name your router resolves (no .local names). "
                "Port 8123 is Home Assistant's own port, nothing else has to be opened. The connection is "
                "unencrypted (ws://) with a generated password, because Easee only accepts TLS certificates "
                "from a public CA."
            ),
            "data": {"ocpp_url": "OCPP address"},
        },
        "connection_failed": {
            "title": "{charger} did not connect",
            "description": (
                "The charger has not connected to {url} within 10 minutes. Possible causes: the address is "
                "not reachable from the charger's network (firewall, VLAN, wrong IP), the name cannot be "
                "resolved, or the charger is offline. Sometimes it just takes longer."
            ),
            "menu_options": {
                "connect": "Wait again",
                "address": "Change the address",
                "rollback": "Cancel and switch the charger back to cloud only",
                "finish": "Save anyway (the charger may connect later)",
            },
        },
    },
    "progress": {
        "wait_for_charger": (
            "OCPP is being enabled for {charger} via the Easee cloud. Waiting until the charger connects "
            "to {url}. This usually takes a few minutes (up to 10)."
        )
    },
    "error": {
        "invalid_url": "Enter a URL like ws://192.168.1.10:8123/api/easee/ocpp",
        "mdns_host": "The charger cannot resolve .local names; use the IP address or a name your router resolves.",
        "wss_not_supported": "wss:// needs a certificate from a public CA, which Home Assistant usually does not have. Use ws://.",
        "wrong_path": "The path must be /api/easee/ocpp (the charger appends its serial number).",
        "ocpp_forbidden": "The Easee cloud refused the change. Only the owner (or an admin) of the site may enable OCPP.",
        "ocpp_rejected": "The Easee cloud rejected the OCPP settings.",
        "cloud_unavailable": "The Easee cloud could not be reached. Try again later.",
        "integration_not_loaded": "The Easee integration is not loaded.",
    },
    "abort": {
        "no_unconfigured_chargers": "All chargers are already connected via OCPP.",
        "integration_not_loaded": "The Easee integration is not loaded.",
        "firmware_too_old": (
            "Firmware {firmware} does not support local OCPP (344 or newer required). "
            "Update the charger in the Easee app first."
        ),
        "rolled_back": "Cancelled. The charger is back on cloud only.",
        "ocpp_forbidden": "The Easee cloud refused the change. Only the owner (or an admin) of the site may change OCPP.",
        "ocpp_rejected": "The Easee cloud rejected the change.",
        "cloud_unavailable": "The Easee cloud could not be reached. Try again later.",
    },
}
SUBENTRY_DE: Texts = {
    "entry_type": "OCPP-Charger",
    "initiate_flow": {
        "user": "Charger per lokalem OCPP verbinden",
        "reconfigure": "OCPP-Adresse ändern",
    },
    "step": {
        "user": {
            "title": "Charger per lokalem OCPP verbinden",
            "description": (
                "Der Charger verbindet sich direkt mit Home Assistant (OCPP 1.6). "
                "Die Easee-Cloud funktioniert parallel weiter. Wähle den Charger:"
            ),
            "data": {"serial": "Charger"},
        },
        "prerequisites": {
            "title": "Voraussetzungen prüfen – {charger}",
            "description": (
                "{firmware_check} Firmware {firmware} (mindestens 344)\n"
                "{wifi_check} Per WLAN verbunden (über Mobilfunk erreicht der Charger Home Assistant nicht)\n"
                "{operator_check} Betreiber des Standorts: {operator} (muss Easee sein; sonst in der Easee-App ändern)\n"
                "{circuit_check} Kein dynamisches Stromkreislimit unterhalb der Absicherung\n\n"
                "Wichtig: Solange OCPP aktiv ist, lädt der Charger erst, wenn Home Assistant die RFID-Karte "
                "freigegeben hat. Lege deine Karten als Tags an (Einstellungen → Tags, Tag-ID = Karten-ID); "
                "der Sensor 'Letzte RFID-Karte' zeigt die ID einer vorgehaltenen Karte."
            ),
            "data": {"reset_circuit_limit": "Dynamisches Stromkreislimit auf die Absicherung anheben"},
            "data_description": {
                "reset_circuit_limit": "Sonst begrenzt das Stromkreislimit aus der Cloud weiterhin die OCPP-Limits."
            },
        },
        "address": {
            "title": "Adresse von Home Assistant – {charger}",
            "description": (
                "Der Charger verbindet sich mit dieser Adresse und hängt /{serial} an. Sie muss aus dem Netz "
                "des Chargers erreichbar sein: IP-Adresse oder ein Name, den dein Router auflöst (keine "
                ".local-Namen). Port 8123 ist der eigene Port von Home Assistant, es muss nichts weiter "
                "freigegeben werden. Die Verbindung ist unverschlüsselt (ws://) mit generiertem Passwort, "
                "weil Easee TLS nur mit Zertifikaten einer öffentlichen CA akzeptiert."
            ),
            "data": {"ocpp_url": "OCPP-Adresse"},
        },
        "connection_failed": {
            "title": "{charger} hat sich nicht verbunden",
            "description": (
                "Der Charger hat sich nicht innerhalb von 10 Minuten mit {url} verbunden. Mögliche Ursachen: "
                "Die Adresse ist aus dem Netz des Chargers nicht erreichbar (Firewall, VLAN, falsche IP), der "
                "Name lässt sich nicht auflösen, oder der Charger ist offline. Manchmal dauert es auch länger."
            ),
            "menu_options": {
                "connect": "Weiter warten",
                "address": "Adresse ändern",
                "rollback": "Abbrechen und Charger wieder nur über die Cloud betreiben",
                "finish": "Trotzdem speichern (der Charger verbindet sich evtl. später)",
            },
        },
    },
    "progress": {
        "wait_for_charger": (
            "OCPP wird für {charger} über die Easee-Cloud eingeschaltet. Warte, bis sich der Charger mit "
            "{url} verbindet. Das dauert meist ein paar Minuten (bis zu 10)."
        )
    },
    "error": {
        "invalid_url": "Gib eine URL wie ws://192.168.1.10:8123/api/easee/ocpp ein.",
        "mdns_host": "Der Charger kann keine .local-Namen auflösen; nutze die IP-Adresse oder einen Namen, den dein Router auflöst.",
        "wss_not_supported": "wss:// braucht ein Zertifikat einer öffentlichen CA, das Home Assistant meist nicht hat. Nutze ws://.",
        "wrong_path": "Der Pfad muss /api/easee/ocpp lauten (der Charger hängt seine Seriennummer an).",
        "ocpp_forbidden": "Die Easee-Cloud hat die Änderung abgelehnt. Nur der Besitzer (oder ein Admin) des Standorts darf OCPP einschalten.",
        "ocpp_rejected": "Die Easee-Cloud hat die OCPP-Einstellungen abgelehnt.",
        "cloud_unavailable": "Die Easee-Cloud ist nicht erreichbar. Versuche es später noch einmal.",
        "integration_not_loaded": "Die Easee-Integration ist nicht geladen.",
    },
    "abort": {
        "no_unconfigured_chargers": "Alle Charger sind bereits per OCPP verbunden.",
        "integration_not_loaded": "Die Easee-Integration ist nicht geladen.",
        "firmware_too_old": (
            "Firmware {firmware} unterstützt kein lokales OCPP (mindestens 344). "
            "Aktualisiere den Charger zuerst in der Easee-App."
        ),
        "rolled_back": "Abgebrochen. Der Charger läuft wieder nur über die Cloud.",
        "ocpp_forbidden": "Die Easee-Cloud hat die Änderung abgelehnt. Nur der Besitzer (oder ein Admin) des Standorts darf OCPP ändern.",
        "ocpp_rejected": "Die Easee-Cloud hat die Änderung abgelehnt.",
        "cloud_unavailable": "Die Easee-Cloud ist nicht erreichbar. Versuche es später noch einmal.",
    },
}


DEVICE_FIELD_EN = {
    "name": "Charger",
    "description": "Charger connected via local OCPP.",
}
DEVICE_FIELD_DE = {
    "name": "Charger",
    "description": "Per lokalem OCPP verbundener Charger.",
}


SERIAL_FIELD_EN = {
    "name": "Serial number",
    "description": "Alternative to the charger: its serial number.",
}
SERIAL_FIELD_DE = {
    "name": "Seriennummer",
    "description": "Alternativ zum Charger: dessen Seriennummer.",
}


def serial_field(device_field: dict[str, str]) -> dict[str, str]:
    """Serial number as alternative target, in the language of the device field."""
    return SERIAL_FIELD_DE if device_field is DEVICE_FIELD_DE else SERIAL_FIELD_EN


def service(name: str, description: str, device_field: dict[str, str], **fields: tuple[str, str]) -> Texts:
    """Texts of one action; fields are (name, description) pairs."""
    return {
        "name": name,
        "description": description,
        "fields": {"device_id": device_field, "serial": serial_field(device_field)}
        | {
            key: {"name": field_name, "description": field_description}
            for key, (field_name, field_description) in fields.items()
        },
    }


SERVICES_EN: Texts = {
    "set_current_limit": service(
        "set temporary current limit",
        "Limits the charger for the given duration; afterwards the OCPP max current applies again. "
        "Meant for controllers (e.g. PV surplus charging) that renew the limit regularly.",
        DEVICE_FIELD_EN,
        current=("Current", "Limit in amperes; 0 pauses charging."),
        duration=("Duration", "Seconds until the limit expires unless it is renewed."),
    ),
    "get_configuration": service(
        "read configuration",
        "Reads all configuration keys, or one key (also hidden Easee keys like FreeCharging).",
        DEVICE_FIELD_EN,
        key=("Key", "Only this key; empty for all visible keys."),
    ),
    "change_configuration": service(
        "change configuration",
        "Writes one configuration key (ChangeConfiguration).",
        DEVICE_FIELD_EN,
        key=("Key", "Configuration key."),
        value=("Value", "New value as text."),
    ),
    "set_charging_profile": service(
        "set charging profile",
        "Installs a charging profile (SetChargingProfile, amperes only on Easee).",
        DEVICE_FIELD_EN,
        connector_id=("Connector", "0 = whole charger, 1 = vehicle connector."),
        charging_profile=("Charging profile", "OCPP 1.6 ChargingProfile object."),
    ),
    "clear_charging_profile": service(
        "clear charging profiles",
        "Removes charging profiles; without criteria all of them.",
        DEVICE_FIELD_EN,
        profile_id=("Profile id", "Only this profile."),
        connector_id=("Connector", "Only this connector."),
        purpose=("Purpose", "Only profiles with this purpose."),
        stack_level=("Stack level", "Only this stack level."),
    ),
    "get_composite_schedule": service(
        "read effective schedule",
        "Returns the limits in force (GetCompositeSchedule).",
        DEVICE_FIELD_EN,
        connector_id=("Connector", "0 = whole charger, 1 = vehicle connector."),
        duration=("Duration", "Period to report, in seconds."),
    ),
    "trigger_message": service(
        "request message",
        "Asks the charger to send a message now (TriggerMessage).",
        DEVICE_FIELD_EN,
        message=("Message", "Message to send."),
        connector_id=("Connector", "Optional connector."),
    ),
    "send_local_list": service(
        "send local authorization list",
        "Cards the charger accepts by itself while it cannot reach Home Assistant (Easee: max. 10).",
        DEVICE_FIELD_EN,
        id_tags=("RFID cards", "Card ids."),
        version=("Version", "List version, increase with every change."),
        full_update=("Replace list", "Replace the list instead of adding to it."),
    ),
    "get_local_list_version": service(
        "read local list version",
        "Returns the version of the local authorization list.",
        DEVICE_FIELD_EN,
    ),
}
SERVICES_DE: Texts = {
    "set_current_limit": service(
        "befristetes Stromlimit setzen",
        "Begrenzt den Charger für die angegebene Dauer; danach gilt wieder der OCPP-Maximalstrom. "
        "Gedacht für Regler (z. B. PV-Überschussladen), die das Limit regelmäßig erneuern.",
        DEVICE_FIELD_DE,
        current=("Strom", "Limit in Ampere; 0 pausiert das Laden."),
        duration=("Dauer", "Sekunden, bis das Limit ohne Erneuerung abläuft."),
    ),
    "get_configuration": service(
        "Konfiguration lesen",
        "Liest alle Konfigurationsschlüssel oder einen (auch versteckte Easee-Schlüssel wie FreeCharging).",
        DEVICE_FIELD_DE,
        key=("Schlüssel", "Nur diesen Schlüssel; leer für alle sichtbaren."),
    ),
    "change_configuration": service(
        "Konfiguration ändern",
        "Schreibt einen Konfigurationsschlüssel (ChangeConfiguration).",
        DEVICE_FIELD_DE,
        key=("Schlüssel", "Konfigurationsschlüssel."),
        value=("Wert", "Neuer Wert als Text."),
    ),
    "set_charging_profile": service(
        "Ladeprofil setzen",
        "Installiert ein Ladeprofil (SetChargingProfile, bei Easee nur Ampere).",
        DEVICE_FIELD_DE,
        connector_id=("Anschluss", "0 = ganzer Charger, 1 = Fahrzeuganschluss."),
        charging_profile=("Ladeprofil", "OCPP-1.6-ChargingProfile-Objekt."),
    ),
    "clear_charging_profile": service(
        "Ladeprofile löschen",
        "Entfernt Ladeprofile; ohne Kriterien alle.",
        DEVICE_FIELD_DE,
        profile_id=("Profil-ID", "Nur dieses Profil."),
        connector_id=("Anschluss", "Nur dieser Anschluss."),
        purpose=("Zweck", "Nur Profile mit diesem Zweck."),
        stack_level=("Stack-Ebene", "Nur diese Ebene."),
    ),
    "get_composite_schedule": service(
        "wirksamen Zeitplan lesen",
        "Liefert die geltenden Limits (GetCompositeSchedule).",
        DEVICE_FIELD_DE,
        connector_id=("Anschluss", "0 = ganzer Charger, 1 = Fahrzeuganschluss."),
        duration=("Dauer", "Zeitraum in Sekunden."),
    ),
    "trigger_message": service(
        "Nachricht anfordern",
        "Fordert den Charger auf, sofort eine Nachricht zu senden (TriggerMessage).",
        DEVICE_FIELD_DE,
        message=("Nachricht", "Zu sendende Nachricht."),
        connector_id=("Anschluss", "Optionaler Anschluss."),
    ),
    "send_local_list": service(
        "lokale Freigabeliste senden",
        "Karten, die der Charger selbst akzeptiert, solange er Home Assistant nicht erreicht (Easee: max. 10).",
        DEVICE_FIELD_DE,
        id_tags=("RFID-Karten", "Karten-IDs."),
        version=("Version", "Listenversion, bei jeder Änderung erhöhen."),
        full_update=("Liste ersetzen", "Liste ersetzen statt ergänzen."),
    ),
    "get_local_list_version": service(
        "Version der lokalen Liste lesen",
        "Liefert die Version der lokalen Freigabeliste.",
        DEVICE_FIELD_DE,
    ),
}


def repair_issue(
    title: str,
    description: str,
    fix_title: str,
    fix_description: str,
    url_label: str,
    errors: dict[str, str],
    aborts: dict[str, str],
) -> Texts:
    """Texts of one repair issue with the re-apply fix flow.

    Fixable issues carry their description in the fix flow step (hassfest rule).
    """
    return {
        "title": title,
        "fix_flow": {
            "step": {
                "init": {
                    "title": fix_title,
                    "description": description + "\n\n" + fix_description,
                    "data": {"ocpp_url": url_label},
                }
            },
            "error": errors,
            "abort": aborts,
        },
    }


FIX_EN = (
    "Apply the connection again – {serial}",
    "Home Assistant will send this address and the stored password to the charger via the Easee cloud. "
    "It usually takes a few minutes until the charger connects.",
    "OCPP address",
)
FIX_DE = (
    "Verbindung erneut anwenden – {serial}",
    "Home Assistant schickt diese Adresse und das gespeicherte Passwort über die Easee-Cloud an den Charger. "
    "Meist dauert es ein paar Minuten, bis er sich verbindet.",
    "OCPP-Adresse",
)
ISSUE_ABORTS_EN = {"charger_not_configured": "The charger is no longer connected via OCPP."}
ISSUE_ABORTS_DE = {"charger_not_configured": "Der Charger ist nicht mehr per OCPP eingerichtet."}


def issues(
    fix: tuple[str, str, str],
    errors: dict[str, str],
    aborts: dict[str, str],
    disconnected: tuple[str, str],
    authentication: tuple[str, str],
    address: tuple[str, str],
) -> Texts:
    """All OCPP repair issues of one language."""
    return {
        "disconnected": repair_issue(*disconnected, *fix, errors, aborts),
        "authentication_failed": repair_issue(*authentication, *fix, errors, aborts),
        "address_changed": repair_issue(*address, *fix, errors, aborts),
    }


ISSUES_EN: Texts = issues(
    FIX_EN,
    SUBENTRY_EN["error"],
    ISSUE_ABORTS_EN,
    (
        "Easee charger {serial} is not connected via OCPP",
        "The charger has not been connected to Home Assistant for more than 15 minutes. While OCPP is active it "
        "cannot start charging without Home Assistant. Check that it is online and can reach Home Assistant, "
        "or apply the connection again.",
    ),
    (
        "Easee charger {serial} uses a wrong OCPP password",
        "The charger tried to connect several times with a password that does not match. Apply the connection "
        "again to send it the stored password.",
    ),
    (
        "OCPP address of Easee charger {serial} no longer points to Home Assistant",
        "The charger connects to {url}, which does not resolve to this Home Assistant any more (e.g. after an IP "
        "change). Apply a current address.",
    ),
)
ISSUES_DE: Texts = issues(
    FIX_DE,
    SUBENTRY_DE["error"],
    ISSUE_ABORTS_DE,
    (
        "Easee-Charger {serial} ist nicht per OCPP verbunden",
        "Der Charger ist seit mehr als 15 Minuten nicht mit Home Assistant verbunden. Solange OCPP aktiv ist, kann "
        "er ohne Home Assistant keinen Ladevorgang starten. Prüfe, ob er online ist und Home Assistant erreicht, "
        "oder wende die Verbindung erneut an.",
    ),
    (
        "Easee-Charger {serial} nutzt ein falsches OCPP-Passwort",
        "Der Charger hat sich mehrfach mit einem nicht passenden Passwort angemeldet. Wende die Verbindung erneut "
        "an, um ihm das gespeicherte Passwort zu schicken.",
    ),
    (
        "OCPP-Adresse von Easee-Charger {serial} zeigt nicht mehr auf Home Assistant",
        "Der Charger verbindet sich mit {url}; die Adresse führt nicht mehr zu diesem Home Assistant (z. B. nach "
        "einem IP-Wechsel). Wende eine aktuelle Adresse an.",
    ),
)

OPTIONS_EN = {"accept_all_cards": "Accept every RFID card (not only the cards registered as tags)"}
OPTIONS_DE = {"accept_all_cards": "Jede RFID-Karte akzeptieren (nicht nur die als Tags angelegten)"}

CONFIG_EN: Texts = {
    "step": {
        "user": {
            "title": "Easee account",
            "description": "Log in with your Easee account. It is used to switch the chargers to local OCPP "
            "and back; at runtime everything stays local.",
            "data": {"username": "E-mail or phone number", "password": "Password"},
        },
        "reauth_confirm": {
            "title": "Easee login expired",
            "description": "Enter the current password of {username}.",
            "data": {"password": "Password"},
        },
    },
    "error": {
        "invalid_auth": "Login failed. Check e-mail/phone number and password.",
        "cloud_unavailable": "The Easee cloud could not be reached. Try again later.",
    },
    "abort": {
        "already_configured": "This Easee account is already set up.",
        "reauth_successful": "Login updated.",
    },
}
CONFIG_DE: Texts = {
    "step": {
        "user": {
            "title": "Easee-Konto",
            "description": "Melde dich mit deinem Easee-Konto an. Es wird nur genutzt, um die Charger auf lokales "
            "OCPP um- und zurückzustellen; im Betrieb bleibt alles lokal.",
            "data": {"username": "E-Mail oder Telefonnummer", "password": "Passwort"},
        },
        "reauth_confirm": {
            "title": "Easee-Anmeldung abgelaufen",
            "description": "Gib das aktuelle Passwort von {username} ein.",
            "data": {"password": "Passwort"},
        },
    },
    "error": {
        "invalid_auth": "Anmeldung fehlgeschlagen. Prüfe E-Mail/Telefonnummer und Passwort.",
        "cloud_unavailable": "Die Easee-Cloud ist nicht erreichbar. Versuche es später noch einmal.",
    },
    "abort": {
        "already_configured": "Dieses Easee-Konto ist bereits eingerichtet.",
        "reauth_successful": "Anmeldung aktualisiert.",
    },
}


def language_texts(
    entity_names_by_platform: dict[str, dict[str, str]],
    status_states: dict[str, str],
    subentry: Texts,
    options: dict[str, str],
    services: Texts,
    issue_texts: Texts,
) -> Texts:
    """Bundle all OCPP texts of one language."""
    entities = entity_names(entity_names_by_platform)
    entities["sensor"]["status"]["state"] = status_states
    return {
        "entity": entities,
        "subentry": subentry,
        "options": options,
        "services": services,
        "issues": issue_texts,
    }


def translation_document(texts: Texts, config: Texts) -> Texts:
    """The complete translation file of one language."""
    return {
        "config": config,
        "options": {"step": {"init": {"data": texts["options"]}}},
        "config_subentries": {"charger": texts["subentry"]},
        "entity": texts["entity"],
        "services": texts["services"],
        "issues": texts["issues"],
    }


def write(path: Path, document: Texts) -> None:
    """Write one translation file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """Write strings.json, translations/en.json and translations/de.json."""
    english = translation_document(
        language_texts(ENTITY_NAMES_EN, STATUS_STATES_EN, SUBENTRY_EN, OPTIONS_EN, SERVICES_EN, ISSUES_EN), CONFIG_EN
    )
    german = translation_document(
        language_texts(ENTITY_NAMES_DE, STATUS_STATES_DE, SUBENTRY_DE, OPTIONS_DE, SERVICES_DE, ISSUES_DE), CONFIG_DE
    )
    write(INTEGRATION_DIR / "strings.json", english)
    write(INTEGRATION_DIR / "translations" / "en.json", english)
    write(INTEGRATION_DIR / "translations" / "de.json", german)


if __name__ == "__main__":
    main()
