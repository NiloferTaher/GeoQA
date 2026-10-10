# `archive`

Archive (ZIP) inspection and pre-extraction validation.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_archive` | Report archive conditions, before anything is extracted. |

## Conditions emitted

### `archive_absolute_path`

**Severity** critical &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member name is an absolute path. Extracting it writes to that absolute location rather than inside the target folder.

**Repair.** Do not extract unfiltered. Strip the leading path component and extract selectively.

### `archive_content_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A member's content does not match its extension. A saved error page or an HTML response stored as a shapefile is the usual cause.

**Repair.** Re-download. The file is not the format its name claims and will not open.

### `archive_decompression_bomb`

**Severity** high &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member expands by an extreme ratio, or past the declared size limit. Classic decompression-bomb shape.

**Repair.** Do not extract. Identify what the member actually is before allowing any write, and check the source of the download.

### `archive_duplicate_member`

**Severity** medium &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

Two members share a name. Most extractors silently keep one of them, so which lands is decided without notice.

**Repair.** Extract members by index or rebuild the archive with unique names.

### `archive_encrypted_member`

**Severity** high &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member is encrypted, so extraction will prompt for a password or fail.

**Repair.** Confirm the password through an approved channel before extracting. Do not enter credentials into an untrusted prompt.

### `archive_excessive_total_size`

**Severity** high &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

The archive as a whole expands past the declared total-size limit for unattended extraction.

**Repair.** Extract selectively by member name and extension rather than unpacking the whole archive.

### `archive_incomplete_shapefile`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A shapefile set is missing one of .shp, .shx or .dbf. A shapefile needs all three before it can be opened.

**Repair.** Recover the missing sidecars from the original source. A .shp on its own is unusable.

### `archive_member_unreadable`

**Severity** medium &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member could not be decompressed. The archive is damaged or was written by a tool using an unsupported method.

**Repair.** Re-download, or extract with a tool that supports the compression method recorded in the archive.

### `archive_nested_archive`

**Severity** low &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

The archive contains another archive. It is listed rather than opened.

**Repair.** Inspect the nested archive separately if its contents are needed.

### `archive_no_geospatial_content`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The archive holds nothing recognisably geospatial, so extracting it for spatial work will not help.

**Repair.** Confirm the download was the one intended.

### `archive_path_traversal`

**Severity** critical &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member name traverses out of the extraction directory. Extracting it writes outside the intended folder.

**Repair.** Do not extract. Inspect the member list and extract only the members you intend, with their names rewritten.

### `archive_unsafe_member_name`

**Severity** medium &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

An archive member has a name that should not be written, such as an empty name or a bare drive specification.

**Repair.** Skip this member and extract the rest selectively.

### `archive_vector_missing_crs`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A vector file inside the archive has no recorded coordinate reference system, so its coordinates cannot be trusted.

**Repair.** Obtain the .prj or .qpj from the source, or record the CRS explicitly alongside the data.

## Design notes

- **Why this exists**
- **Design constraints**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
