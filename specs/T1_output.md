## Output format

Reply with ONE JSON object and nothing else (no markdown fences, no commentary).

For an ORTHOGRAPHIC edit:
{"orthographic": true, "label": "R:ORTH" | "WO:ORTH",
 "subtype": "phon" | "shape" | "complex" | "order" | "punc"}

For every other edit:
{"orthographic": false, "operation": "M" | "R" | "U" | "WO",
 "domain": "LEX-CONT" | "LEX-FUNC" | "SYNT",
 "pos": "VERB" | "NOUN" | "ADJ" | "ADV" | "PART" | "AUX" | "PREP" | "CLF" | "CONJ" | "X",
 "extension": "<CODE:item>" | "none"}

The extension CODE must be one of: TEMP, ADD, CONT, LINK, DEG, LOC, ASP, FOC,
CONST, ARG, COMP, STR, NEG, MIX, LEX. Lexical-content errors may take
"LEX:syn", "LEX:colloc", or "LEX:coinage", or "none" when no refinement
applies. Use pinyin for the item part of other codes (e.g., "ASP:le",
"TEMP:cai-jiu").
