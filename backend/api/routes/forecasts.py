from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from amadeus import Client, ResponseError
from backend.core.config import get_settings

router = APIRouter(prefix="/flights", tags=["flights"])

def amadeus_client() -> Client:
    s = get_settings()
    return Client(
        client_id=s.AMADEUS_API_KEY,
        client_secret=s.AMADEUS_API_SECRET
    )

def _normalize_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    price = offer.get("price", {})
    itineraries = offer.get("itineraries", [])
    first_itin = itineraries[0] if itineraries else {}
    segments: List[Dict[str, Any]] = first_itin.get("segments", [])
    first_seg = segments[0] if segments else {}
    last_seg = segments[-1] if segments else {}

    marketing_carrier = first_seg.get("carrierCode")
    departure = first_seg.get("departure", {})
    arrival = last_seg.get("arrival", {})
    duration = first_itin.get("duration")  # e.g. "PT1H25M"
    stops = max(len(segments) - 1, 0)

    return {
        "airline_code": marketing_carrier,
        "depart_at": departure.get("at"),
        "depart_iata": departure.get("iataCode"),
        "arrive_at": arrival.get("at"),
        "arrive_iata": arrival.get("iataCode"),
        "duration": duration,
        "stops": stops,
        "price_total": price.get("total"),
        "currency": price.get("currency"),
        "raw": offer,
    }

@router.get("/search")
def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: str = Query(..., description="YYYY-MM-DD"),
    adults: int = 1,
    currency: str = "PHP",
) -> Dict[str, Any]:
    am = amadeus_client()
    try:
        resp = am.shopping.flight_offers_search.get(
            originLocationCode=origin.upper(),
            destinationLocationCode=destination.upper(),
            departureDate=date,
            adults=adults,
            currencyCode=currency.upper(),
        )
        offers = [ _normalize_offer(o) for o in resp.data ]
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "date": date,
            "currency": currency.upper(),
            "count": len(offers),
            "offers": offers,
        }
    except ResponseError as e:
        raise HTTPException(status_code=502, detail=str(e))
