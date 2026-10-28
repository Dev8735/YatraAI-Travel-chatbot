"""Transport information providers.

No schedule/fare/availability source is bundled. The interface exists so a verified
provider (e.g. a licensed railway data API) can be plugged in; until then the assistant
explains the limitation and links to official sources instead of inventing timetables.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.travel import OfficialLink, TransportInfo

OFFICIAL_LINKS = {
    "TRAIN": [
        OfficialLink(label="IRCTC — official Indian Railways ticketing", url="https://www.irctc.co.in/"),
        OfficialLink(label="NTES — National Train Enquiry System (running status, schedules)",
                     url="https://enquiry.indianrail.gov.in/mntes/"),
    ],
    "FLIGHT": [
        OfficialLink(label="Airports Authority of India — flight information", url="https://www.aai.aero/"),
    ],
    "BUS": [
        OfficialLink(label="GSRTC — Gujarat state buses (for routes within Gujarat; other states run their own RTCs)", url="https://gsrtc.in/"),
    ],
}


class TransportProvider(Protocol):
    name: str
    is_live: bool

    async def lookup(self, *, mode: str | None, origin: str | None, destination: str | None) -> TransportInfo: ...


class NoTransportProvider:
    name = "none"
    is_live = False

    async def lookup(self, *, mode: str | None, origin: str | None, destination: str | None) -> TransportInfo:
        mode = mode or "TRAIN"
        noun = {"TRAIN": "train", "FLIGHT": "flight", "BUS": "bus"}.get(mode, "transport")
        message = (f"I don't have a live {noun} schedule or fare source connected, so I can't confirm specific "
                   f"{noun} numbers, timings, fares or seat availability. Please check the official sources below "
                   f"before booking.")
        links = OFFICIAL_LINKS.get(mode, OFFICIAL_LINKS["TRAIN"])
        return TransportInfo(provider=self.name, available=False, mode=mode, origin=origin,
                             destination=destination, message=message, official_links=links)
