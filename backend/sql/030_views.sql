-- 030_views.sql
-- Views for API consumption with proper JSON formatting

-- Events view with structured venue and address objects
CREATE OR REPLACE VIEW v_events_api AS
SELECT
    event_id,
    title,
    description,
    start_time,
    end_time,
    all_day,
    jsonb_build_object(
        'name', venue_name,
        'address', jsonb_build_object(
            'street', address_street,
            'city', address_city,
            'state', address_state,
            'zip', address_zip
        ),
        'latitude', latitude,
        'longitude', longitude
    ) AS venue,
    url,
    jsonb_build_object(
        'name', organizer_name,
        'contact', organizer_contact
    ) AS organizer,
    source,
    source_ref,
    region,
    updated_at
FROM event_canonical
ORDER BY updated_at DESC, event_id;

-- Businesses view with structured address object
CREATE OR REPLACE VIEW v_businesses_api AS
SELECT
    business_id,
    name,
    category,
    jsonb_build_object(
        'street', address_street,
        'city', address_city,
        'state', address_state,
        'zip', address_zip
    ) AS address,
    latitude,
    longitude,
    website,
    phone,
    email,
    self_identified_muslim_owned,
    halal_certified,
    certifier_name,
    certifier_ref,
    placekey,
    source,
    source_ref,
    region,
    updated_at
FROM business_canonical
ORDER BY updated_at DESC, business_id;

-- Metrics view for aggregated statistics
CREATE OR REPLACE VIEW v_metrics AS
SELECT
    (SELECT COUNT(*) FROM event_canonical) AS events_count,
    (SELECT COUNT(*) FROM business_canonical) AS businesses_count,
    (SELECT COUNT(DISTINCT address_city) FROM event_canonical) +
    (SELECT COUNT(DISTINCT address_city) FROM business_canonical) AS cities_covered,
    (SELECT MAX(completed_at) FROM build_metadata WHERE status = 'success') AS last_build_at;

-- City statistics view
CREATE OR REPLACE VIEW v_city_stats AS
SELECT
    'event' AS entity_type,
    address_city AS city,
    COUNT(*) AS count
FROM event_canonical
GROUP BY address_city
UNION ALL
SELECT
    'business' AS entity_type,
    address_city AS city,
    COUNT(*) AS count
FROM business_canonical
GROUP BY address_city
ORDER BY entity_type, count DESC;

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('030_views') ON CONFLICT DO NOTHING;
