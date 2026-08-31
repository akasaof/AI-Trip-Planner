from app.tools.attractions import attraction_search
from app.tools.currency import currency_convert
from app.tools.flights import flight_search
from app.tools.hotels import hotel_search
from app.tools.maps import map_distance
from app.tools.rag_tool import rag_search
from app.tools.restaurants import restaurant_search
from app.tools.weather import weather_lookup

ALL_TOOLS = [
    flight_search,
    hotel_search,
    restaurant_search,
    attraction_search,
    weather_lookup,
    map_distance,
    currency_convert,
    rag_search,
]

__all__ = ["ALL_TOOLS"]
