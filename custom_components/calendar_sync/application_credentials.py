"""Application Credentials für Google Calendar OAuth."""
from __future__ import annotations

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"


async def async_get_authorization_server(
    hass: HomeAssistant,
) -> AuthorizationServer:
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    return {
        "console_url": "https://console.cloud.google.com/apis/credentials",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
