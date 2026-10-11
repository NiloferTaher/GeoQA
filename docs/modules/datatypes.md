# `datatypes`

Declared datatypes, geometry parts, and what a database will accept.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_datatypes` | Report columns whose declared type does not match what they hold. |
| `validate_geometry_parts` | Report mixed geometry part structure and a declared type that will not accept it. |

## Conditions emitted

### `datatype_identifier_as_float`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

An identifier column is declared as a float, so it is written as 70677.0 by some readers and 70677 by others and stops matching itself.

**Repair.** Declare the column as text or as an integer. Integers are correct when the identifier is genuinely numeric; text is correct when it may carry a prefix.

### `datatype_identifier_as_text`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

An identifier column is declared as text, so trailing whitespace and inconsistent padding make equal identifiers compare unequal.

**Repair.** Trim and normalise the values at load, and add a uniqueness constraint so the problem cannot recur silently.

### `datatype_numeric_as_text`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A coordinate or measure column is declared as text, which admits a comma decimal separator and stray whitespace as though they were valid numbers.

**Repair.** Declare the column as a numeric type. A text column containing numbers is not a weaker constraint, it is a different and incorrect one.

### `geometry_declared_type_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The geometry column is declared as one type but the layer contains another, so the database will refuse the insert rather than coerce it.

**Repair.** Either widen the declared column to accept the observed type or convert the data. Widening to a generic geometry column accepts everything and constrains nothing, so prefer the conversion.

### `geometry_empty_part`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A multi-part geometry contains an empty part, which contributes nothing and is the signature of a dissolve that did not complete.

**Repair.** Drop the empty part, or redo the operation that produced it. Note that constructing such a geometry through shapely silently discards the empty part, so one can only arrive here by being decoded from stored bytes.

### `geometry_family_mixed`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A single layer contains more than one geometry family, such as both points and polygons.

**Repair.** Split the layer by family. Choosing the majority family silently discards every feature that did not match it.

### `geometry_part_type_mixed`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A single layer contains more than one geometry type, or a multi-part geometry holds parts of unlike type.

**Repair.** Agree one part type for the layer, or accept the mixture knowingly if the destination format supports it.

### `postgis_crs_not_epsg`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

The CRS does not resolve to an EPSG code, so every consumer must carry the full definition with it.

**Repair.** Reproject to an EPSG-coded CRS if the destination permits it, or record the full definition as part of the delivery.

### `postgis_crs_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

The layer has no CRS, so PostGIS will store the geometry with SRID 0 rather than refusing it.

**Repair.** Declare the CRS before loading. An SRID of 0 is not an error and is not noticed until something downstream projects it.

### `postgis_srid_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The layer's SRID differs from the target. PostGIS does not reproject on insert.

**Repair.** Reproject before the load. PostGIS stores the SRID alongside the coordinates as given and will happily store coordinates that are wrong for it.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
