-- Migration 0002: Add indexes on foreign key columns
-- Addresses audit finding: missing FK indexes cause sequential scans on JOINs.

CREATE INDEX IF NOT EXISTS idx_documents_work_id ON documents(work_id);
CREATE INDEX IF NOT EXISTS idx_sections_document_id ON sections(document_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent_section_id ON sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_blocks_section_id ON blocks(section_id);
CREATE INDEX IF NOT EXISTS idx_entity_labels_entity_id ON entity_labels(entity_id);
CREATE INDEX IF NOT EXISTS idx_mentions_block_id ON mentions(block_id);
CREATE INDEX IF NOT EXISTS idx_mentions_entity_id ON mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_block_alignments_source ON block_alignments(source_block_id);
CREATE INDEX IF NOT EXISTS idx_block_alignments_target ON block_alignments(target_block_id);

-- Prevent duplicate mention of same entity in same block+language
CREATE UNIQUE INDEX IF NOT EXISTS idx_mentions_unique
    ON mentions(block_id, entity_id, language);
