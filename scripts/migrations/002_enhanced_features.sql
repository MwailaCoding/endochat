-- EndoChat Enhanced Features Migration
-- Migration 002: Add tables for shareable cards, support groups, stories, and candles

-- =============================================================================
-- SHARED CARDS (Shareable Answer Cards)
-- =============================================================================

CREATE TABLE IF NOT EXISTS shared_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    card_type TEXT NOT NULL DEFAULT 'fact',
    title TEXT,
    content TEXT NOT NULL,
    image_url TEXT NOT NULL,
    qr_code_url TEXT,
    tracking_code TEXT UNIQUE NOT NULL,
    clicks INTEGER DEFAULT 0,
    platform_shares JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_shared_cards_tracking_code ON shared_cards(tracking_code);
CREATE INDEX IF NOT EXISTS idx_shared_cards_created_at ON shared_cards(created_at DESC);

-- =============================================================================
-- SUPPORT GROUPS
-- =============================================================================

CREATE TABLE IF NOT EXISTS support_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    group_types TEXT[] DEFAULT ARRAY['in-person'],
    country TEXT,
    city TEXT,
    address TEXT,
    latitude FLOAT,
    longitude FLOAT,
    contact_info JSONB DEFAULT '{}',
    website TEXT,
    meeting_schedule TEXT,
    member_count INTEGER DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    submitted_by_session TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_groups_location ON support_groups(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_support_groups_country_city ON support_groups(country, city);
CREATE INDEX IF NOT EXISTS idx_support_groups_verified ON support_groups(verified) WHERE verified = TRUE;

CREATE TABLE IF NOT EXISTS group_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES support_groups(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(group_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_group_reviews_group_id ON group_reviews(group_id);

CREATE TABLE IF NOT EXISTS group_joins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES support_groups(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(group_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_group_joins_group_id ON group_joins(group_id);

-- =============================================================================
-- ANONYMOUS STORIES
-- =============================================================================

CREATE TABLE IF NOT EXISTS stories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    title TEXT,
    author_name TEXT DEFAULT 'Anonymous Warrior',
    location TEXT,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    session_id TEXT,
    supports INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    featured BOOLEAN DEFAULT FALSE,
    moderated BOOLEAN DEFAULT TRUE,
    hidden BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stories_supports ON stories(supports DESC);
CREATE INDEX IF NOT EXISTS idx_stories_featured ON stories(featured) WHERE featured = TRUE;
CREATE INDEX IF NOT EXISTS idx_stories_moderated ON stories(moderated, hidden);

CREATE TABLE IF NOT EXISTS story_supports (
    story_id UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (story_id, session_id)
);

CREATE TABLE IF NOT EXISTS story_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    from_session TEXT,
    message TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_story_messages_story_id ON story_messages(story_id);
CREATE INDEX IF NOT EXISTS idx_story_messages_created_at ON story_messages(created_at DESC);

-- =============================================================================
-- VIRTUAL CANDLE CEREMONY
-- =============================================================================

CREATE TABLE IF NOT EXISTS candles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    message TEXT,
    dedication TEXT,
    location TEXT,
    color TEXT DEFAULT 'yellow',
    lit_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    lit_date DATE GENERATED ALWAYS AS ((lit_at AT TIME ZONE 'UTC')::date) STORED
);

CREATE INDEX IF NOT EXISTS idx_candles_lit_at ON candles(lit_at DESC);
CREATE INDEX IF NOT EXISTS idx_candles_session_date ON candles(session_id, lit_date);

-- Unique constraint: one candle per session per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_candles_session_day_unique 
    ON candles(session_id, lit_date);

CREATE TABLE IF NOT EXISTS candle_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candle_id UUID REFERENCES candles(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    from_session TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candle_messages_candle_id ON candle_messages(candle_id);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to calculate Haversine distance (in km)
CREATE OR REPLACE FUNCTION haversine_distance(
    lat1 FLOAT, lon1 FLOAT,
    lat2 FLOAT, lon2 FLOAT
) RETURNS FLOAT AS $$
DECLARE
    r FLOAT := 6371; -- Earth's radius in km
    dlat FLOAT;
    dlon FLOAT;
    a FLOAT;
    c FLOAT;
BEGIN
    dlat := radians(lat2 - lat1);
    dlon := radians(lon2 - lon1);
    a := sin(dlat / 2) ^ 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ^ 2;
    c := 2 * atan2(sqrt(a), sqrt(1 - a));
    RETURN r * c;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to tables with updated_at
DROP TRIGGER IF EXISTS update_support_groups_updated_at ON support_groups;
CREATE TRIGGER update_support_groups_updated_at
    BEFORE UPDATE ON support_groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_stories_updated_at ON stories;
CREATE TRIGGER update_stories_updated_at
    BEFORE UPDATE ON stories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
