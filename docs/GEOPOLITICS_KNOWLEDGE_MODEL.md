# Geopolitical Knowledge Model

## Purpose

The Geopolitical Watch knowledge layer stores durable analytical knowledge separately from the event/evidence layer. Its job is to answer: **what concepts, historical mechanisms, regional structures and strategic dependencies help interpret this episode?** It must never answer **did this event occur?** without evidence-layer support.

## Four-layer separation

1. **Evidence** — observed publications, coded datasets, institutional reports and sensors.
2. **Claims** — normalized statements supported, disputed, corrected or retracted by evidence.
3. **Episodes** — persistent conflict/intelligence objects linking claims and evidence.
4. **Knowledge context** — theories, concepts, historical cases, regions and structural relationships used for interpretation.

Knowledge is always emitted with `context_not_evidence=true`.

## Knowledge node types

### School
A theoretical family such as realism, liberal institutionalism or constructivism.

### Concept
An analytical mechanism such as security dilemma, deterrence, economic statecraft, strategic chokepoint or proxy warfare.

### Region
A structured regional context with countries, strategic themes and persistent geographic dependencies.

### Case study
A historical episode used for analogy. Each case must include `analogy_limits`.

### Source
A canonical legal, official-data, academic, bibliographic or specialist source entry.

## Matching rules

The context engine uses only transparent deterministic matching in v0.8:

- canonical country membership;
- resolved entity canonical names/types;
- episode title and recent-event text;
- claim types/statements;
- concept keywords;
- infrastructure/chokepoint aliases.

A match does not prove causation. It creates a candidate context node and a set of analytical questions.

## Output contract

Each episode may receive:

```json
{
  "strategic_context": {
    "context_not_evidence": true,
    "matched_concepts": [],
    "regional_context": [],
    "historical_analogies": [],
    "analytical_questions": [],
    "source_registry_version": "geowatch-geopolitics-sources-v1",
    "knowledge_version": "geowatch-geopolitics-knowledge-v1"
  }
}
```

## Historical analogy governance

Historical analogy is high-risk for false confidence. Therefore:

- at least one shared mechanism is required;
- the engine must emit the analogy's limitations;
- no prediction may be generated solely from an analogy;
- the current episode must retain independent evidence and current-source analysis;
- the system should prefer multiple competing analogies over a single deterministic precedent.

## Multi-theory rule

When a matched concept can be interpreted by different theoretical schools, reports should preserve the alternatives. Example: an alliance expansion may be read as balancing under realism, institution-building under liberalism, or identity/community formation under constructivism. The system should not silently choose one explanation.

## Knowledge update governance

A new durable knowledge item requires:

1. stable identifier;
2. node type;
3. original summary written for Geopolitical Watch;
4. source references;
5. date added and date reviewed;
6. confidence in the summary, separate from source quality;
7. known counterarguments or alternative theories;
8. operational questions it helps answer;
9. tests for deterministic matching when used by code.

## Copyright and source discipline

The repository may store:

- official public texts where permitted;
- structured metadata;
- citations and bibliographic records;
- original summaries and analytical notes;
- short quotations within applicable limits.

It must not mirror copyrighted books, articles or paywalled research.

## Future extensions

v0.9+ may add:

- vector retrieval over original summaries;
- temporal validity of knowledge nodes;
- country strategic profiles;
- rivalry and alliance graphs;
- causal graphs with typed relations;
- forecast hypotheses linked to outcome calibration;
- analyst-approved knowledge proposals generated from resolved review cases.
