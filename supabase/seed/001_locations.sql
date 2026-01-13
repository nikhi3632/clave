-- ============================================================
-- Seed: Restaurant Locations
-- ============================================================

INSERT INTO locations (name, street, city, state, zip_code, location_type) VALUES
    ('Downtown', '123 Main St', 'New York', 'NY', '10001', 'downtown'),
    ('Airport', '456 Terminal Blvd', 'Jamaica', 'NY', '11430', 'airport'),
    ('Mall', '789 Shopping Center Dr', 'New York', 'NY', '10019', 'mall'),
    ('University', '321 College Ave', 'New York', 'NY', '10027', 'university')
ON CONFLICT (name) DO UPDATE SET
    street = EXCLUDED.street,
    city = EXCLUDED.city,
    state = EXCLUDED.state,
    zip_code = EXCLUDED.zip_code,
    location_type = EXCLUDED.location_type;
