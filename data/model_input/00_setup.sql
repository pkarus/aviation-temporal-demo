-- DATA-04a canonical temporal model-input layer: shared setup.
--
-- Scope: PK_AVIATION_TEMPORAL.MODEL_INPUT only.  SOURCE and VALIDATION are read-only here.
--
-- Conventions frozen by SOURCE_CONTRACT.md / SEMANTIC_DECISIONS.md and implemented below:
--   * half-open state and knowledge intervals: valid_from <= d < valid_to;
--   * source sentinel DATE '9999-12-31' means unknown future and never becomes a bound;
--   * model open sentinel DATE '9999-01-01' is derived only;
--   * DV-43 uses D-0012 grammar `dv43-lp-v1`: frame(x) = octet_length(x) || ':' || x, and each
--     field contributes frame(field_id) || frame(snowflake_type_tag) || frame('N')
--     or frame(field_id) || frame(type_tag) || frame('V') || frame(canonical_value).
--     The SS-40 column in SOURCE.SCHEDULE_SNAPSHOT is a live known-answer vector for this grammar
--     and the verification gate recomputes all of it.

CREATE SCHEMA IF NOT EXISTS PK_AVIATION_TEMPORAL.MODEL_INPUT
  COMMENT = 'DATA-04a canonical temporal model-input layer consumed by the RelationalAI ontology (MODEL-01). Deterministic derivations of PK_AVIATION_TEMPORAL.SOURCE; not golden-answer tables.';

-- ---------------------------------------------------------------------------------------------
-- DV-43 / DV-44 / DV-46 serialization primitives (D-0012 `dv43-lp-v1`).
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION MODEL_INPUT.LP(S TEXT)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 length-prefixed frame: octet_length(s) || '':'' || s. Null in, null out.'
  AS $$ TO_VARCHAR(OCTET_LENGTH(S)) || ':' || S $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_NUM(V NUMBER(38,0))
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical NUMBER(38,0) encoding: base 10, no padding.'
  AS $$ TO_VARCHAR(V) $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_FLOAT(V FLOAT)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical FLOAT encoding (lossless canonical decimal, Python repr equivalent). Integral values render with a trailing .0; the verification gate proves every contracted FLOAT input is integral so this branch is exact for the shipped fixtures.'
  AS $$
    CASE
      WHEN V IS NULL THEN NULL
      WHEN V = TRUNC(V) AND ABS(V) < 1e16 THEN TO_VARCHAR(CAST(V AS NUMBER(38,0))) || '.0'
      ELSE TO_VARCHAR(V)
    END $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_BOOL(V BOOLEAN)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical BOOLEAN encoding: true|false.'
  AS $$ IFF(V, 'true', 'false') $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_DATE(V DATE)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical DATE encoding: ISO YYYY-MM-DD.'
  AS $$ TO_VARCHAR(V, 'YYYY-MM-DD') $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_TIME(V TIME)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical TIME encoding: ISO HH:MM:SS at full stored precision. The verification gate proves zero sub-second components in the shipped fixtures.'
  AS $$ TO_VARCHAR(V, 'HH24:MI:SS') $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.CANON_TS(V TIMESTAMP_NTZ)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'D-0012 canonical TIMESTAMP_NTZ encoding: ISO YYYY-MM-DDTHH:MM:SS, no invented timezone.'
  AS $$ TO_VARCHAR(V, 'YYYY-MM-DD"T"HH24:MI:SS') $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.DV43_FIELD(FIELD_ID TEXT, TYPE_TAG TEXT, CANON TEXT)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'One DV-43 field contribution. A distinct N/V frame keeps SQL NULL separate from the VARCHAR text NULL.'
  AS $$
    MODEL_INPUT.LP(FIELD_ID) || MODEL_INPUT.LP(TYPE_TAG)
      || IFF(CANON IS NULL, MODEL_INPUT.LP('N'), MODEL_INPUT.LP('V') || MODEL_INPUT.LP(CANON))
  $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.NULL_SAFE_TOKEN(CANON TEXT)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'Null-safe watched-value token used for IS DISTINCT FROM style change detection over composite signatures.'
  AS $$ IFF(CANON IS NULL, MODEL_INPUT.LP('N'), MODEL_INPUT.LP('V') || MODEL_INPUT.LP(CANON)) $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.NORMALIZE_SOURCE_DATE(V DATE)
  RETURNS DATE LANGUAGE SQL IMMUTABLE
  COMMENT = 'Source sentinel 9999-12-31 (unknown future) normalizes to NULL. The companion *_is_unknown_future flag retains the evidence. Model open sentinel 9999-01-01 is never produced here.'
  AS $$ IFF(V = DATE '9999-12-31', NULL, V) $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.IS_UNKNOWN_FUTURE(V DATE)
  RETURNS BOOLEAN LANGUAGE SQL IMMUTABLE
  COMMENT = 'True only when the raw source date equals the source unknown-future sentinel 9999-12-31.'
  AS $$ V = DATE '9999-12-31' $$;

CREATE OR REPLACE FUNCTION MODEL_INPUT.DISPLAY_FLOAT(V FLOAT)
  RETURNS TEXT LANGUAGE SQL IMMUTABLE
  COMMENT = 'Display rendering used for schedule old/new change values: integral floats render without a fractional part.'
  AS $$
    CASE
      WHEN V IS NULL THEN NULL
      WHEN V = TRUNC(V) AND ABS(V) < 1e16 THEN TO_VARCHAR(CAST(V AS NUMBER(38,0)))
      ELSE TO_VARCHAR(V)
    END $$;
