"""
Central configuration, loaded from environment variables / .env.

All provider keys below are for free tiers (see README for signup links).
Every tool in app/tools/ requires its real key to return data — there is
no mock/simulated fallback in this build. If a key is missing, the tool
returns an empty result and the reason is surfaced back to the user
rather than silently faked.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"

    # LLM (Groq / LangChain)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 3500
    llm_tool_loop_max_tokens: int = 700

    # MongoDB (local via Compass by default, or point at Atlas instead)
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "trip_planner"

    # Live provider APIs (all free tier)
    travelpayouts_token: str = ""       # flights + hotels (Aviasales/Hotellook cached price data)
    travelpayouts_marker: str = ""      # your Travelpayouts affiliate/partner ID
    geoapify_api_key: str = ""          # restaurants + attractions (Geoapify Places, OSM-backed)
    openweather_api_key: str = ""       # weather
    openrouteservice_api_key: str = ""  # maps/distance
    google_maps_api_key: str = ""       # optional: used for map_distance AND the frontend embed if set
    stayingapi_key: str = ""
    request_timeout_seconds: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
