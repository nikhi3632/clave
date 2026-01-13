-- ============================================================
-- Phase 8: Dynamic Locations Support
-- ============================================================
-- Removes hardcoded location_type constraint to allow
-- locations to be created dynamically from source data.

-- Drop the hardcoded CHECK constraint on location_type
-- This allows any location type, not just the 4 hardcoded values
DO $$
BEGIN
    ALTER TABLE locations DROP CONSTRAINT IF EXISTS locations_location_type_check;
EXCEPTION
    WHEN undefined_object THEN
        -- Constraint doesn't exist, that's fine
        NULL;
END $$;

-- Make location_type nullable (it was implicitly nullable but let's be explicit)
ALTER TABLE locations ALTER COLUMN location_type DROP NOT NULL;

-- Add comment explaining the change
COMMENT ON COLUMN locations.location_type IS 'Optional venue type descriptor. No longer constrained to specific values - can be any string or NULL.';
