-- Migration 0003: Explicit block order within a section.
-- Existing works keep current order by backfilling from created_at.

ALTER TABLE blocks ADD COLUMN IF NOT EXISTS order_index INTEGER;

UPDATE blocks b
SET order_index = sub.rn
FROM (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY section_id ORDER BY created_at, id) AS rn
    FROM blocks
) sub
WHERE b.id = sub.id
  AND b.order_index IS NULL;
