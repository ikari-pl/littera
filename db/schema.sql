-- Littera Database Schema
-- Literature meets refactoring.
--
-- This schema encodes stable identity and semantic structure.
-- Derived data must live elsewhere.

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================
-- Core Identity Tables
-- =====================

CREATE TABLE works (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    title TEXT,
    description TEXT,
    default_language TEXT,
    metadata JSONB
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    title TEXT,
    order_index INTEGER,
    metadata JSONB
);

CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_section_id UUID REFERENCES sections(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    title TEXT,
    order_index INTEGER,
    metadata JSONB
);

CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    block_type TEXT NOT NULL,
    language TEXT NOT NULL,
    source_text TEXT NOT NULL,
    metadata JSONB
);

-- =====================
-- Semantic Model
-- =====================

CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    entity_type TEXT NOT NULL,
    canonical_label TEXT,
    properties JSONB,
    status TEXT,
    notes TEXT
);

CREATE TABLE entity_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    base_form TEXT NOT NULL,
    aliases JSONB,
    UNIQUE (entity_id, language)
);

CREATE TABLE mentions (

    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    block_id UUID NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    features JSONB,
    surface_form TEXT
);

-- =====================
-- Entity Work Metadata (future use)
-- =====================

CREATE TABLE entity_work_metadata (
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    metadata JSONB,
    PRIMARY KEY (entity_id, work_id)
);

-- =====================
-- Derived Structures
-- =====================

CREATE TABLE block_alignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_block_id UUID NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    target_block_id UUID NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    alignment_type TEXT,
    confidence NUMERIC,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    scope TEXT,
    scope_id UUID,
    issue_type TEXT,
    description TEXT,
    severity TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

COMMIT;
