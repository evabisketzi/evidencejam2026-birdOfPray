# Stage-1 comparison: ours vs teammate's (offline, no LLM)

papers: 308; teammate preprocessing fell back to ours on 0
input tokens (our tokenizer, whole TITLE/SPECIES/CONTEXT/TEXT): ours 1,659,884 (median 4915.0), team 1,822,308 (median 5404.5); ratio team/ours 1.10
numbered sentences: ours 34,895, team 39,273

- murphy2005 / ours: sentences 70, input tokens 4047; gold edges whose cited sentence is available to the model: by offsets 0/72, by text (first 60 chars) 1/72
- murphy2005 / team: sentences 73, input tokens 3882; gold edges whose cited sentence is available to the model: by offsets 0/72, by text (first 60 chars) 1/72
- 4CB9X9XE / ours: sentences 68, input tokens 3766; gold edges whose cited sentence is available to the model: by offsets 38/48, by text (first 60 chars) 38/48
- 4CB9X9XE / team: sentences 77, input tokens 4665; gold edges whose cited sentence is available to the model: by offsets 46/48, by text (first 60 chars) 46/48