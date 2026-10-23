"""Reparatur-Flow: blockierte Löschungen freigeben oder stattdessen wiederherstellen."""
from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class PendingDeletionsFlow(RepairsFlow):
    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    def _coordinator(self):
        return self.hass.data.get(DOMAIN, {}).get(self._entry_id)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        coordinator = self._coordinator()
        if coordinator is None or not coordinator.pending_deletions:
            return self.async_abort(reason="no_pending")
        return self.async_show_menu(
            step_id="init",
            menu_options=["approve", "restore"],
            description_placeholders={
                "count": str(len(coordinator.pending_deletions)),
                "events": coordinator.pending_summary(),
            },
        )

    async def async_step_approve(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        coordinator = self._coordinator()
        if coordinator is None:
            return self.async_abort(reason="no_pending")
        await coordinator.async_approve_deletions()
        return self.async_create_entry(data={})

    async def async_step_restore(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        coordinator = self._coordinator()
        if coordinator is None:
            return self.async_abort(reason="no_pending")
        await coordinator.async_restore_pending()
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    return PendingDeletionsFlow((data or {})["entry_id"])
