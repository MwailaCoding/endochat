"""Support group finder service."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.services.utils.logging import get_logger
from app.core.exceptions import EndoChatException

logger = get_logger(__name__)


class SupportGroupError(EndoChatException):
    """Support group service error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail, error_code="SUPPORT_GROUP_ERROR")


@dataclass
class SupportGroup:
    """Support group data model."""

    id: UUID
    name: str
    description: Optional[str]
    group_types: List[str]
    country: Optional[str]
    city: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    contact_info: dict
    website: Optional[str]
    meeting_schedule: Optional[str]
    member_count: int
    verified: bool
    active: bool
    created_at: datetime
    distance_km: Optional[float] = None


class SupportGroupFinder:
    """Service for finding and managing support groups."""

    def __init__(self, db_pool):
        """Initialize with database pool."""
        self.db_pool = db_pool
        self._geocoder = None

    @property
    def geocoder(self):
        """Lazy-load geocoder."""
        if self._geocoder is None:
            self._geocoder = Nominatim(user_agent="endochat_support_groups")
        return self._geocoder

    async def geocode_location(self, location: str) -> Optional[tuple[float, float]]:
        """
        Geocode a location string to coordinates.

        Args:
            location: City name, address, or location string

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        try:
            result = self.geocoder.geocode(location, timeout=10)
            if result:
                return (result.latitude, result.longitude)
            return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning("Geocoding failed", location=location, error=str(e))
            return None

    async def search_groups(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location: Optional[str] = None,
        radius_km: float = 50.0,
        group_types: Optional[List[str]] = None,
        verified_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[SupportGroup], int]:
        """
        Search for support groups by location.

        Args:
            latitude: Search center latitude
            longitude: Search center longitude
            location: Location string to geocode (if no lat/lng)
            radius_km: Search radius in kilometers
            group_types: Filter by group types
            verified_only: Only return verified groups
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (groups list, total count)
        """
        if latitude is None or longitude is None:
            if location:
                coords = await self.geocode_location(location)
                if coords:
                    latitude, longitude = coords
                else:
                    return await self._search_by_name(
                        location, group_types, verified_only, limit, offset
                    )
            else:
                return await self._get_all_groups(
                    group_types, verified_only, limit, offset
                )

        query = """
            WITH filtered_groups AS (
                SELECT 
                    id, name, description, group_types, country, city, address,
                    latitude, longitude, contact_info, website, meeting_schedule,
                    member_count, verified, active, created_at,
                    haversine_distance($1, $2, latitude, longitude) as distance_km
                FROM support_groups
                WHERE active = TRUE
                    AND latitude IS NOT NULL
                    AND longitude IS NOT NULL
                    AND haversine_distance($1, $2, latitude, longitude) <= $3
        """
        params = [latitude, longitude, radius_km]
        param_idx = 4

        if verified_only:
            query += " AND verified = TRUE"

        if group_types:
            query += f" AND group_types && ${param_idx}::text[]"
            params.append(group_types)
            param_idx += 1

        query += f"""
            )
            SELECT *, COUNT(*) OVER() as total_count
            FROM filtered_groups
            ORDER BY distance_km ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        if not rows:
            return [], 0

        total = rows[0]["total_count"] if rows else 0
        groups = [self._row_to_group(row) for row in rows]

        return groups, total

    async def _search_by_name(
        self,
        search_term: str,
        group_types: Optional[List[str]],
        verified_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[List[SupportGroup], int]:
        """Search groups by name/city when geocoding fails."""
        query = """
            WITH filtered_groups AS (
                SELECT 
                    id, name, description, group_types, country, city, address,
                    latitude, longitude, contact_info, website, meeting_schedule,
                    member_count, verified, active, created_at,
                    NULL::float as distance_km
                FROM support_groups
                WHERE active = TRUE
                    AND (
                        city ILIKE $1
                        OR country ILIKE $1
                        OR name ILIKE $1
                    )
        """
        params = [f"%{search_term}%"]
        param_idx = 2

        if verified_only:
            query += " AND verified = TRUE"

        if group_types:
            query += f" AND group_types && ${param_idx}::text[]"
            params.append(group_types)
            param_idx += 1

        query += f"""
            )
            SELECT *, COUNT(*) OVER() as total_count
            FROM filtered_groups
            ORDER BY verified DESC, member_count DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        if not rows:
            return [], 0

        total = rows[0]["total_count"] if rows else 0
        groups = [self._row_to_group(row) for row in rows]

        return groups, total

    async def _get_all_groups(
        self,
        group_types: Optional[List[str]],
        verified_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[List[SupportGroup], int]:
        """Get all groups without location filter."""
        query = """
            WITH filtered_groups AS (
                SELECT 
                    id, name, description, group_types, country, city, address,
                    latitude, longitude, contact_info, website, meeting_schedule,
                    member_count, verified, active, created_at,
                    NULL::float as distance_km
                FROM support_groups
                WHERE active = TRUE
        """
        params = []
        param_idx = 1

        if verified_only:
            query += " AND verified = TRUE"

        if group_types:
            query += f" AND group_types && ${param_idx}::text[]"
            params.append(group_types)
            param_idx += 1

        query += f"""
            )
            SELECT *, COUNT(*) OVER() as total_count
            FROM filtered_groups
            ORDER BY verified DESC, member_count DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        if not rows:
            return [], 0

        total = rows[0]["total_count"] if rows else 0
        groups = [self._row_to_group(row) for row in rows]

        return groups, total

    async def get_group(self, group_id: UUID) -> Optional[SupportGroup]:
        """Get a single support group by ID."""
        query = """
            SELECT 
                id, name, description, group_types, country, city, address,
                latitude, longitude, contact_info, website, meeting_schedule,
                member_count, verified, active, created_at,
                NULL::float as distance_km
            FROM support_groups
            WHERE id = $1 AND active = TRUE
        """
        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(query, group_id)

        if row:
            return self._row_to_group(row)
        return None

    async def add_group(
        self,
        name: str,
        description: Optional[str],
        group_types: List[str],
        country: Optional[str],
        city: Optional[str],
        address: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
        contact_info: dict,
        website: Optional[str],
        meeting_schedule: Optional[str],
        submitted_by_session: str,
    ) -> UUID:
        """
        Add a new support group (unverified).

        If only city/country provided, attempt to geocode.
        """
        if latitude is None and longitude is None and city:
            location_str = f"{city}, {country}" if country else city
            coords = await self.geocode_location(location_str)
            if coords:
                latitude, longitude = coords

        query = """
            INSERT INTO support_groups (
                name, description, group_types, country, city, address,
                latitude, longitude, contact_info, website, meeting_schedule,
                submitted_by_session, verified
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, FALSE)
            RETURNING id
        """
        import json

        async with self.db_pool.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                name,
                description,
                group_types,
                country,
                city,
                address,
                latitude,
                longitude,
                json.dumps(contact_info),
                website,
                meeting_schedule,
                submitted_by_session,
            )
        return row["id"]

    async def join_group(self, group_id: UUID, session_id: str) -> bool:
        """
        Track a user joining a group.

        Returns True if this is a new join, False if already joined.
        """
        query = """
            INSERT INTO group_joins (group_id, session_id)
            VALUES ($1, $2)
            ON CONFLICT (group_id, session_id) DO NOTHING
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            result = await conn.fetchrow(query, group_id, session_id)

        if result:
            await self._increment_member_count(group_id)
            return True
        return False

    async def add_review(
        self,
        group_id: UUID,
        session_id: str,
        rating: int,
        review_text: Optional[str],
    ) -> bool:
        """
        Add or update a review for a group.

        Returns True if successful.
        """
        if rating < 1 or rating > 5:
            raise SupportGroupError(
                message="Invalid rating",
                detail="Rating must be between 1 and 5",
            )

        query = """
            INSERT INTO group_reviews (group_id, session_id, rating, review_text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (group_id, session_id)
            DO UPDATE SET rating = $3, review_text = $4
            RETURNING id
        """
        async with self.db_pool.pool.acquire() as conn:
            result = await conn.fetchrow(query, group_id, session_id, rating, review_text)
        return result is not None

    async def get_group_reviews(
        self,
        group_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """Get reviews for a group."""
        query = """
            SELECT rating, review_text, created_at
            FROM group_reviews
            WHERE group_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        async with self.db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, group_id, limit, offset)

        return [
            {
                "rating": row["rating"],
                "review_text": row["review_text"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def _increment_member_count(self, group_id: UUID):
        """Increment the member count for a group."""
        query = """
            UPDATE support_groups
            SET member_count = member_count + 1
            WHERE id = $1
        """
        async with self.db_pool.pool.acquire() as conn:
            await conn.execute(query, group_id)

    def _row_to_group(self, row) -> SupportGroup:
        """Convert a database row to SupportGroup."""
        import json

        contact_info = row["contact_info"]
        if isinstance(contact_info, str):
            contact_info = json.loads(contact_info)

        return SupportGroup(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            group_types=row["group_types"] or [],
            country=row["country"],
            city=row["city"],
            address=row["address"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            contact_info=contact_info or {},
            website=row["website"],
            meeting_schedule=row["meeting_schedule"],
            member_count=row["member_count"] or 0,
            verified=row["verified"],
            active=row["active"],
            created_at=row["created_at"],
            distance_km=row["distance_km"],
        )
