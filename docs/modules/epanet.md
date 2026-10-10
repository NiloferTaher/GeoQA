# `epanet`

EPANET ``.inp`` input-file parsing and structural validation.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_inp` | Structural and referential validation of a parsed deck. |

## Conditions emitted

### `epanet_dangling_endpoint`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A link names a node that does not exist in the network.

**Repair.** Add the missing node or correct the identifier. A dangling endpoint either fails to load or leaves the link unresolved.

### `epanet_disconnected_component`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Part of the network is not reachable from any supply, so it has no pressure regime and contributes no flow.

**Repair.** Connect the component to the supply or state that it is intentionally isolated, such as a future extension placeholder.

### `epanet_duplicate_id`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Two or more objects share an identifier within one EPANET section, so a reference resolves ambiguously.

**Repair.** Reassign unique identifiers. Duplicates silently bind a link or pattern to whichever object the parser reads first.

### `epanet_empty_section`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A required EPANET section is present but contains no entries.

**Repair.** Populate the section or record deliberately that the network has no such elements; an empty section usually means an incomplete export.

### `epanet_invalid_diameter`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Pipe diameter is non-positive or outside the range EPANET can represent.

**Repair.** Correct the diameter and confirm the units it was entered in.

### `epanet_missing_reactions`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Pipe wall reaction is absent, so the roughness relationship the model expects is not established.

**Repair.** Declare a reaction type. Where the file relies on an EPANET default, record that dependency rather than leaving it implicit.

### `epanet_missing_section`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A required EPANET input section is absent, so the model cannot be simulated as written.

**Repair.** Add the missing section. Confirm which EPANET version the network is authored for, since required sections differ between them.

### `epanet_non_default_reaction_order`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Reaction coefficients are not supplied in the order EPANET expects, so they will be read against the wrong variable.

**Repair.** Reorder to the documented order for the declared reaction type. Values are otherwise accepted and produce wrong hydraulics.

### `epanet_non_numeric_field`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A field that EPANET parses as a number contains a non-numeric value.

**Repair.** Correct the value or quote the field if EPANET treats it as a comment for this section.

### `epanet_orphaned_node`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A junction or reservoir is referenced by no link, so it is isolated and contributes no hydraulics.

**Repair.** Connect the node or remove it. Check whether the omission is a truncated export rather than a modelling decision.

### `epanet_unit_mismatch`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Flow units declared in the file are inconsistent with the magnitudes in the data.

**Repair.** Correct the units declaration or convert the data. A unit mismatch produces plausible-looking results at physically wrong magnitudes.

### `epanet_unknown_pattern`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

An object references a demand or head pattern that is not defined.

**Repair.** Define the pattern or repoint the reference. An unresolved pattern silently falls back to a constant, which changes results without warning.

### `epanet_unknown_units`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The file declares flow units that are not recognised, so dimensional behaviour cannot be established.

**Repair.** Declare one of the EPANET flow unit systems explicitly rather than relying on a default.

### `epanet_zero_length_pipe`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A pipe has zero length, which implies infinite or undefined hydraulic gradient for its flow.

**Repair.** Supply real geometry or a declared length. A zero-length pipe usually results from missing coordinates rather than a genuine zero.

## Design notes

- **Scope, deliberately**
- **Section handling**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
