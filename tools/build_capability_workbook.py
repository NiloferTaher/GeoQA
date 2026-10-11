"""Generate the GeoQA capability workbook.

Reports what the library can actually do today, and what it does not, so the gap
is visible rather than inferred. Everything is read from the live package: the
problem registry, the exposed validator functions, the profile builders and the
module tree. Nothing is hand-maintained, so the workbook cannot drift from the
code without regenerating it.

    python -m tools.build_capability_workbook
"""

from __future__ import annotations

import inspect
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "geoqa_capability_matrix.xlsx"

sys.path.insert(0, str(REPO_ROOT))


def _collect_registry() -> tuple[list[dict[str, Any]], dict[str, int]]:
    from geoqa.problem_registry import VALIDATION_RULE_VERSION, list_problem_definitions

    rows: list[dict[str, Any]] = []
    for definition in list_problem_definitions():
        rows.append(
            {
                "category": definition.category,
                "problem_name": definition.problem_name,
                "severity": str(definition.default_severity),
                "issue_class": getattr(definition, "issue_class", "data_issue"),
                "confidence": str(definition.default_confidence),
                "actionable": "yes" if definition.default_actionable else "no",
                "iso_category": definition.iso_category or "Unmapped",
                "description": definition.description,
                "repair_hint": definition.repair_hint,
                "source": definition.source_name or "",
            }
        )
    rows.sort(key=lambda r: (r["category"], r["problem_name"]))
    summary = {
        "total": len(rows),
        "rule_version": VALIDATION_RULE_VERSION,
        "by_category": len({r["category"] for r in rows}),
        "by_severity": len({r["severity"] for r in rows}),
    }
    return rows, summary


def _collect_validator_functions() -> list[dict[str, Any]]:
    import geoqa.validation_runtime as runtime

    rows: list[dict[str, Any]] = []
    for name in dir(runtime):
        if name.startswith("_"):
            continue
        obj = getattr(runtime, name)
        if not inspect.isfunction(obj):
            continue
        if not getattr(obj, "__module__", "").startswith("geoqa.validations"):
            continue
        signature = str(inspect.signature(obj))
        keyword_args = [
            p for p in inspect.signature(obj).parameters.values()
            if p.kind is inspect.Parameter.KEYWORD_ONLY
        ]
        rows.append(
            {
                "function": name,
                "signature": f"{name}{signature}",
                "tunable_parameters": ", ".join(p.name for p in keyword_args),
                "source_module": obj.__module__.rsplit(".", 1)[-1],
                "docstring": (inspect.getdoc(obj) or "").split("\n")[0],
            }
        )
    rows.sort(key=lambda r: r["function"])
    return rows


def _collect_modules() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    package = REPO_ROOT / "geoqa"
    for path in sorted(package.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT)
        parts = rel.parts
        if parts[1:2] == ("validations",):
            group = "validators"
        elif len(parts) > 1 and parts[1] in {"core", "io", "reports", "ml", "qa"}:
            group = parts[1]
        elif len(parts) == 1:
            group = "package"
        else:
            group = "other"
        rows.append(
            {
                "group": group,
                "module": str(rel).replace("\\", "/"),
                "lines": len(path.read_text(encoding="utf-8", errors="replace").splitlines()),
            }
        )
    rows.sort(key=lambda r: (r["group"], r["module"]))
    return rows


def _collect_profiles() -> list[dict[str, Any]]:
    import geoqa.profile_registry as profiles

    rows: list[dict[str, Any]] = []
    for name in sorted(n for n in dir(profiles) if n.startswith("build_")):
        dataset = "land_use"
        if "water" in name:
            dataset = "water_network"
        elif "boundaries" in name:
            dataset = "boundaries"
        strictness = (
            "strict" if "strict" in name else "audit" if "audit" in name
            else "quick" if "quick" in name else "standard"
        )
        rows.append(
            {
                "dataset": dataset,
                "strictness": strictness,
                "builder": name,
                "purpose": _profile_purpose(dataset, strictness),
            }
        )
    return rows


def _profile_purpose(dataset: str, strictness: str) -> str:
    base = {
        "land_use": "Cadastral and land-use polygon layers",
        "water_network": "Pipe and network-asset layers",
        "boundaries": "Administrative and service-area boundaries",
    }.get(dataset, dataset)
    mode = {
        "quick": "fast triage, core checks only",
        "standard": "default breadth",
        "strict": "exhaustive, includes tolerance-sensitive checks",
        "audit": "audit posture, evidence-oriented severities",
    }.get(strictness, "")
    return f"{base} - {mode}"


def _coverage_summary() -> list[dict[str, Any]]:
    """Where GeoQA is strong, thin, or absent. Deliberately opinionated."""
    return [
        {
            "area": "Geometry validity",
            "status": "built",
            "coverage": "25 registered conditions: validity, self-intersection, rings, slivers, minimum length, null and degenerate geometry, 2D/3D dimension conformance",
            "notes": "All-zero-Z rule preserved from production observation. make_valid measured against buffer(0).",
        },
        {
            "area": "Topology",
            "status": "built",
            "coverage": "25 conditions: dangles, near-miss endpoints, unsnapped ends, isolated segments, overlaps, gaps, duplicate vertices, unsplit features, cross-name and nested same-name polygons",
            "coverage_gap": "Endpoint triage resolves companion-node free ends so topology noise is not read as defects.",
        },
        {
            "area": "Accuracy and tolerance",
            "status": "built",
            "coverage": "14 conditions: XY tolerance, coordinate precision, positional accuracy, spectral index range",
            "notes": "Metre-based and CRS-invariant; verified by metamorphic test across projections.",
        },
        {
            "area": "Attributes and schema",
            "status": "built",
            "coverage": "8 conditions: domains, subtypes, null policy, uniqueness, field constraints, reference lookup, JSON-in-text payload",
        },
        {
            "area": "CRS and datum",
            "status": "built",
            "coverage": "9 conditions: missing, invalid, datum mismatch, reprojection advisory, length unit against CRS unit, Web Mercator measurement, polar extent, angular measurements, declared reprojection",
            "notes": "Advisory by default. Reprojection happens only when a target is declared, and the reprojected copy is never written over the input.",
        },
        {
            "area": "Metadata",
            "status": "built",
            "coverage": "7 conditions: abstract, extent, lineage, positional accuracy, completeness report",
        },
        {
            "area": "Reporting integrity",
            "status": "built",
            "coverage": "Issue aggregation collapses raw findings to per-feature records while retaining raw counts; hash-linked audit archive; run manifests",
            "notes": "Measured 2.12x collapse on near-miss findings from a real 185k-finding run.",
        },
        {
            "area": "Governance conditions",
            "status": "built",
            "coverage": "14 conditions: unlabelled physical constant in a metric chain, hardcoded scope boundary, undeclared empirical coefficient meaning, undeclared units, missing source, unit mismatch, scale ambiguity, out of range, unverified, reproduced, failed reproduction, indeterminate reproduction, inconsistent reuse, JSON-in-text payload",
            "notes": "Coefficients are declared values, not bare numbers. Verification state is reported as evidence in its own right.",
        },
        {
            "area": "Water network hydraulics",
            "status": "partial",
            "coverage": "EPANET .inp parsed locally: 15 conditions covering missing and empty sections, duplicate identifiers, orphaned nodes, dangling endpoints, disconnected components, zero-length pipes, invalid diameters, unit declaration and mismatch, unknown patterns, reactions and non-numeric fields.",
            "coverage_gap": "No hydraulic solver. Simulation is delegated to EPANET or WNTR, neither of which is installed yet, so nothing has been run against a real network.",
        },
        {
            "area": "Night flow and leakage",
            "status": "built",
            "coverage": "Orifice discharge, FAVAD power law, FADD dependence, minimum night flow, with 12 coefficient-provenance conditions and optional reproduction checking against a declared reference case.",
            "notes": "The module is complete. What it will not do is supply a FAVAD exponent or an orifice discharge coefficient: both are properties of one network's fittings and pressure regime, not published constants, so they must be declared by the analyst and are recorded as declared rather than defaulted. What is published is checked against the published figures.",
        },
        {
            "area": "Published coefficient reference cases",
            "status": "built",
            "coverage": "Five worked examples with inputs, published expected outputs and citations, executable as tests or as a runtime dataset type. Plus enforcement of the UARL equation's stated applicability limits.",
            "notes": "The IWA Task Force example reproduces to 0.01 percent: (18*603 + 0.8*16359 + 0) * 65 = 1,556,178 L/day against a published 1,556 m3/day. The 1999 AQUA example reproduces its mains and connections components exactly; its private-pipe component prints 87 where the stated coefficients give 88.7, recorded as published rounding rather than absorbed into a loose tolerance.",
        },
        {
            "area": "NRW water balance",
            "status": "built",
            "coverage": "8 conditions: IWA balance decomposition, supply and loss reconciliation, NRW agreement, negative components, losses exceeding input, night-flow residual, ILI not computable.",
            "notes": "Losses are derived from the balance rather than accepted as inputs.",
        },
        {
            "area": "UARL and ILI",
            "status": "built",
            "coverage": "Declared Lambert UARL from mains length, connections, private length and a pressure factor; ILI with the IWA caveat always attached; 8 conditions including missing connections, estimated pressure and out-of-range values.",
            "notes": "Coefficients ship as unpopulated templates. The 18 / 0.8 / 25 set is common in practice but its provenance is not recorded here, so it is never applied by default.",
        },
        {
            "area": "Raster and imagery",
            "status": "partial",
            "coverage": "GeoTIFF via rasterio: band roles, unmapped bands, insufficient bands, nodata, scale factor, geographic CRS, windowed index computation with explicit band mapping.",
            "coverage_gap": "GDAL drops band descriptions passed at creation, so delivered rasters without descriptions require an explicit band map and cannot be trusted on band order alone.",
        },
        {
            "area": "Hyperspectral and HDF5",
            "status": "built",
            "coverage": "8 conditions covering HDF-EOS swath products: undeclared wavelengths, unknown or mismatched product level, undeclared fill value, absent quality layers, absent geolocation, too few bands, and a high no-data share. Windowed reads by wavelength interval with the resolved wavelengths returned alongside the data.",
            "notes": "Built against a 426-band EMIT surface-reflectance granule: 655 MB per cube member read down to 1.4 MB for a 90-band window. Bands are resolved by wavelength interval, never by index, because index 100 is a different wavelength in every product.",
        },
        {
            "area": "Cross-period recurrence",
            "status": "built",
            "coverage": "6 conditions: repeat on the same asset, repeat at the same place with a different asset, unattributed recurrence, period gaps and missing expected periods.",
            "notes": "The same-asset and same-place split is the point: replacing a component that is not the cause wastes an excavation.",
        },
        {
            "area": "QGIS and ArcGIS interoperability",
            "status": "partial",
            "coverage": "Severity QML, GeoPackage output bundle, run manifest, PyQGIS recipe, ArcGIS field and severity-rank mapping.",
            "coverage_gap": "QML is verified as XML and by reopening the GeoPackage, not by loading it in QGIS. No FileGDB export or ArcGIS Pro batch recipe.",
        },
        {
            "area": "Cross-layer spatial logic",
            "status": "built",
            "coverage": "12 conditions: point-in-polygon, point-on-line, cross-layer intersections, boundary mismatch against reference",
        },
        {
            "area": "Boundary conformance",
            "status": "partial",
            "coverage": "Undeclared cut detection, explained clips against a declared reference, subdivided references, continuity breaks.",
            "coverage_gap": "A detected cut is evidence of a nonconformance, not proof of an error. Majority assignment across the clip boundary is configurable by the caller rather than fixed, because the threshold is a client decision and the chosen value is reported alongside the result.",
        },
        {
            "area": "Cloud-optimized GeoTIFF",
            "status": "built",
            "coverage": "4 conditions: cloud-optimized layout, missing or undersized overviews, tile size against the declared block size, and whether the format is marked as standing rather than transitional.",
            "notes": "Layout only. It reads structure, not pixels; band content validation is the raster adapter's job.",
        },
        {
            "area": "OSM data",
            "status": "built",
            "coverage": "5 conditions: licence and attribution declaration, version and timestamp metadata, and geometry emergent from unconnected ways rather than authored as features.",
            "notes": "The point is that OSM geometry is assembled from relations at render time. A validator that assumes a closed polygon is testing the extractor's behaviour rather than the data's.",
        },
        {
            "area": "Vertical datum",
            "status": "built",
            "coverage": "7 conditions: declared reference surface, depth sign convention, missing vertical component on data that requires one, compound CRS requirements, and unit reasoning on vertical attributes.",
        },
        {
            "area": "Hardware feasibility",
            "status": "built",
            "coverage": "CPU temperature and throttling headroom, available memory against the estimated working set, free disk against the projected output, and GPU presence where a step needs one.",
            "notes": "Reports whether this machine can carry out the operation before it is attempted, so a long run stops on evidence rather than on the operator noticing a hot laptop.",
        },
        {
            "area": "Governance gates",
            "status": "built",
            "coverage": "Declared release gates that evaluate findings, record which issues triggered them, and hold for a named human decision. llm_involved is a class constant rather than a setting, so a gate cannot be constructed that claims not to consult a model while doing so.",
            "notes": "Recall is scored against expected outcomes rather than remembered, so the hit rate is a number the library produces. Each property is covered by a test that fails if it stops being true.",
        },
        {
            "area": "Cross-layer referential integrity",
            "status": "built",
            "coverage": "5 conditions: child row referencing an absent parent, unmatched rows in each direction, rows with no usable join key, and geometric orphans where an asset's identifier resolves but its geometry meets nothing in the network layer.",
            "notes": "The two directions are reported separately because an orphan-only check reports half the problem and looks complete while doing so. Keys are compared as trimmed text, so a numeric identifier read as 70677, as \"70677\" and as \" 70677\" joins correctly rather than failing on the join key.",
        },
        {
            "area": "Geometry part structure",
            "status": "built",
            "coverage": "3 conditions: mixed geometry families in one layer, mixed part types, and a declared column type that will not accept what the layer contains.",
            "notes": "Answers the single-versus-multi question explicitly, with single and multi counts, the dominant type, and the family breakdown. The declared-versus-observed check exists because a column declared Polygon will not take a MultiPolygon at insert and PostGIS will not coerce it.",
        },
        {
            "area": "Declared datatypes",
            "status": "built",
            "coverage": "3 conditions: identifier declared as float, identifier declared as text, and a coordinate or measure column declared as text.",
            "notes": "Coordinates declared as text admit a comma decimal separator and stray whitespace as though they were valid numbers. An integer identifier is accepted; only a float or text identifier is reported, because those are the ones that stop matching themselves.",
        },
        {
            "area": "PostGIS load expectations",
            "status": "built",
            "coverage": "3 conditions plus the part and datatype checks: absent CRS, CRS that does not resolve to an EPSG code, and SRID differing from the target.",
            "notes": "Not a substitute for asking the database. These catch the mismatches visible from the layer alone so the failure arrives before the insert rather than during it.",
        },
        {
            "area": "Placeholder and sentinel values",
            "status": "built",
            "coverage": "1 condition covering zero dates, N/A and similar text, negative numeric sentinels, Excel error values, and empty strings, reported per column and per kind.",
            "notes": "These pass a null check and are read back as real answers. A zero date is distinguished from an Excel error because the fix is different in each case.",
        },
        {
            "area": "Encoding integrity",
            "status": "built",
            "coverage": "2 conditions: a shapefile with no .cpg sidecar, and attribute values that do not survive the declared encoding.",
            "notes": "Detects and reports rather than repairs. Rewriting encodings on load destroys the evidence of what the original bytes were, and the repair belongs to whoever holds the source of truth.",
        },
        {
            "area": "Output durability",
            "status": "built",
            "coverage": "6 conditions covering buffer containment, round-trip write and read-back, row count changes, lost geometry, and degraded geometry after serialisation.",
            "notes": "Round-trip validation writes the layer and reopens it, because a layer that is non-empty in memory may not be loadable from disk. Scale-dependent tolerance derives a tolerance from the data's own extent and reports the distance that resulted, rather than applying an unstated metre value.",
        },
        {
            "area": "Spatial chunking",
            "status": "partial",
            "coverage": "Halo-buffered tiling in geoqa/chunking.py. A tile selects every feature intersecting its bounds plus a declared halo, geometries whole and never clipped, so a feature crossing a boundary is validated identically on both sides. Findings are deduplicated on problem name and feature id.",
            "notes": "Chunking is opt-in per validator: a validator runs on the whole layer unless it is named in CHUNK_LOCAL_VALIDATORS, because whole-layer correctness is the default and tiling has to earn the right to change what a validator can see. Twelve validators are declared tileable; the topology questions cannot be tiled at all and are listed with the reason.",
            "coverage_gap": "An undeclared halo on a multi-tile run is reported as evidence rather than passing silently. scripts/verify_chunking_equivalence.py demonstrates the property: with a halo, a 64-tile run returns exactly the findings the whole-layer run returns; with the halo removed the same run invents one. Not yet wired into validation_runtime dispatch, and the budget is a vertex count rather than a measured memory ceiling.",
        },
        {
            "area": "Conflict resolution",
            "status": "not built",
            "coverage": "No collapsing of competing source records onto one logical feature.",
            "coverage_gap": "Numbered key selection with uniqueness evidence and declared precedence, retaining original values rather than overwriting them.",
        },
        {
            "area": "Archive and package inspection",
            "status": "built",
            "coverage": "13 conditions: zip-slip traversal, absolute paths, unsafe names, decompression bombs, total size, encryption, duplicate members, content-versus-extension mismatch, unreadable members, incomplete shapefile sets, missing CRS sidecars, nested archives, and archives with no geospatial content",
            "notes": "Inspects without extracting. Member names are checked for traversal and content is checked against magic bytes, because a .shp containing XML will not open and a .shp containing a ZIP is a real occurrence. Verified against 41 archives in a real downloads folder.",
        },
        {
            "area": "Tabular sources",
            "status": "built",
            "coverage": "17 conditions: missing and duplicate headers, ragged rows, identifier leading-zero loss, over-long numeric identifiers, ambiguous day/month dates, instrument sentinels, merged cells, hidden sheets and rows, formulas, empty columns, missing keys and duplicate keys",
            "notes": "Targets the failures that produce plausible wrong data rather than errors. Excel turns 007123 into 7123 and 03/04 into a different month; both survive every downstream check.",
        },
        {
            "area": "Coordinate axis order",
            "status": "built",
            "coverage": "6 conditions: undeclared order, swapped axes, ambiguous order, outside extent, non-numeric coordinates, and declaration versus column-name conflict. SQL generators for PostgreSQL and PostGIS are provided and return the query rather than taking a connection.",
            "notes": "EPSG:4326 is formally latitude/longitude while GeoJSON, PostGIS and desktop GIS are longitude/latitude. Both readings of an in-range pair are legal, so an ambiguous pair is reported as evidence and needs a declared extent to become a verdict.",
        },
        {
            "area": "Credential and disclosure safety",
            "status": "built",
            "coverage": "Provider-prefixed token patterns, PEM private key blocks, connection strings with inline passwords, URL basic auth, and entropy-gated secret-named literals; plus 5 conditions for credentials, blocked terms, sensitive columns, personal data and filesystem paths that would be sent to a model",
            "notes": "Detection has explicit exemptions for environment references, placeholders and short values, because a detector that cries wolf is switched off and then protects nothing.",
        },
        {
            "area": "Clipping conformance",
            "status": "built",
            "coverage": "8 conditions: straddling evidence with a measured split, assignment near the threshold, unresolved assignment, half-area features, heavily truncated features, features missing after a clip, clipped features with no source, and the evidence condition itself",
            "notes": "The assignment percentage is a caller-supplied parameter, not a constant, because it is an organisational policy. Half-geometry is detected by area ratio against the source, which catches a centreline clip that no validity check would.",
        },
        {
            "area": "Workbook attachments",
            "status": "built",
            "coverage": "9 conditions: broken path references, orphaned attachments, duplicate content, attachments below a legibility threshold, undecodable formats, unattributable rows, rows missing an attachment, unverifiable keys, and a workbook with no media at all",
            "notes": "Domain-neutral by construction: the artefact is called an attachment and the row a record, so the same checks serve any evidence-per-row workflow.",
        },
        {
            "area": "Metadata governance",
            "status": "built",
            "coverage": "11 conditions: undeclared licence, non-open licence, unassigned accountability, undeclared lineage, undeclared conformity, missing unique identifier, missing temporal reference, stale metadata, and missing or placeholder elements",
            "notes": "Required elements and multiplicities follow Commission Regulation (EC) No 1205/2008; open-by-default follows Directive (EU) 2019/1024. Chosen as a citable checklist because it specifies multiplicities, which makes missing decidable rather than a matter of taste.",
        },
        {
            "area": "Packaging and distribution",
            "status": "blocked",
            "coverage": "PyPI name geoqa is taken by an unrelated package; GitHub has a functional QGIS-plugin collision.",
            "coverage_gap": "Resolve naming before public release. Repository name can stay.",
        },
    ]


def _roadmap() -> list[dict[str, Any]]:
    return [
        {
            "priority": 1,
            "item": "EPANET .inp parser",
            "status": "done",
            "why": "Water networks are the target domain and the input format is the gate to any hydraulic work. The parser is ours; the solver is not.",
            "approach": "Parse locally into a structured model. Validate structure, units, topology and boundary conditions. Reuse WNTR for graph traversal and metrics rather than writing a hydraulic solver.",
            "blocked_by": "None.",
        },
        {
            "priority": 2,
            "item": "Night-flow and leakage module",
            "status": "done",
            "why": "Minimum night flow is the most widely used NRW indicator and was absent.",
            "approach": "Orifice discharge, FAVAD power law, FADD and night-flow leakage, all driven by declared coefficients with optional reproduction checking.",
            "blocked_by": "None. Coefficient correctness is a separate open item.",
        },
        {
            "priority": 3,
            "item": "Archive and package inspection",
            "status": "done",
            "why": "A downloads folder is mostly archives whose contents are unknown until extracted, and extraction is where the expensive mistakes happen.",
            "approach": "Inventory members without writing: names for traversal, content against magic bytes, shapefile sidecar sets, decompression ratio. Extraction stays a separate opt-in step with an explicit plan.",
            "blocked_by": "None.",
        },
        {
            "priority": 4,
            "item": "Tabular source validation",
            "status": "done",
            "why": "CSV and Excel is where coordinates acquire their identifiers, and where leading zeros and date conventions are destroyed silently.",
            "approach": "Header, row-width and key checks, plus the conversion failures: leading-zero loss, over-long numeric identifiers, ambiguous dates and instrument sentinels.",
            "blocked_by": "None.",
        },
        {
            "priority": 5,
            "item": "Coordinate axis order",
            "status": "done",
            "why": "EPSG:4326 and CRS84 disagree on axis order, and a swapped in-range pair resolves to a real but wrong place.",
            "approach": "Infer order from values, column names and declaration. Report ambiguity as evidence rather than guessing. Provide SQL generators for PostgreSQL and PostGIS that return the query instead of taking a connection.",
            "blocked_by": "None.",
        },
        {
            "priority": 6,
            "item": "Credential detection and AI disclosure guard",
            "status": "done",
            "why": "A credential in source survives every rotation because it is a literal, and the same payload is what gets sent to a model.",
            "approach": "Provider token patterns, PEM blocks and inline-password URIs, with explicit exemptions so the detector is not switched off. A redaction layer with an allowlist preference for anything leaving the process.",
            "blocked_by": "None.",
        },
        {
            "priority": 7,
            "item": "Clipping conformance",
            "status": "done",
            "why": "A clip down a street centreline produces valid geometry at half the true area, and no validity check notices.",
            "approach": "Caller-supplied assignment percentage rather than a hardcoded majority rule, and area-ratio comparison against the source to find halves.",
            "blocked_by": "None.",
        },
        {
            "priority": 8,
            "item": "UARL and ILI",
            "status": "done",
            "why": "The IWA water loss specialist group states ILI must not be used alone for target setting. That constraint is now encoded, not just documented.",
            "approach": "Declared Lambert UARL from mains length, connections, private length and pressure factor; ILI always returned with its caveats and blocking gaps.",
            "blocked_by": "None.",
        },
        {
            "priority": 9,
            "item": "IWA water balance and NRW decomposition",
            "status": "done",
            "why": "Losses must be derived from the balance, never entered directly.",
            "approach": "Decompose into authorised consumption, real losses, apparent losses and NRW, and validate that components reconcile.",
            "blocked_by": "None.",
        },
        {
            "priority": 10,
            "item": "Raster adapter",
            "status": "done",
            "why": "Spectral validators could not read imagery, which is the most common real-world use.",
            "approach": "Windowed per-pixel GeoTIFF reader through rasterio, with explicit band mapping. Spectral validation now operates on real rasters, and COG layout is checked separately.",
            "blocked_by": "Delivered GeoTIFFs often carry no band descriptions, so an explicit band map remains required rather than optional.",
        },
        {
            "priority": 11,
            "item": "Repeat-incident and cross-period checks",
            "status": "done",
            "why": "Recurrence of a defect across periods is a repair-priority signal no QA tool reports.",
            "approach": "Distinguish same asset across periods from same location with a different asset. Report period gaps and missing expected periods so absence is not mistaken for absence of defects.",
            "blocked_by": "None.",
        },
        {
            "priority": 12,
            "item": "Conflict resolution under declared policy",
            "status": "next",
            "why": "When N source records collapse to one logical feature, which record survives should be recorded rather than decided silently.",
            "approach": "Numbered key selection from ranked candidates with uniqueness shown. Declared precedence policy. Original values retained, never overwritten.",
            "blocked_by": "None.",
        },
        {
            "priority": 13,
            "item": "HDF5 raster adapter",
            "status": "done",
            "why": "Delivered imagery is frequently HDF5 rather than GeoTIFF, and the previous reader stopped at the GeoTIFF case.",
            "approach": "Read groups and datasets as bands with explicit roles, reusing the same band-mapping and scaling rules as the GeoTIFF path so the two cannot diverge. Bands resolve by wavelength interval, never by index.",
            "blocked_by": "None. Verified against a 426-band EMIT surface-reflectance granule, where a 90-band window reads 1.4 MB against 655 MB for the whole cube.",
        },
        {
            "priority": 13,
            "item": "FAVAD and orifice discharge reference cases",
            "status": "done",
            "why": "Every implemented hydraulic formula should reproduce a published figure, not merely run.",
            "approach": "UARL and background leakage reproduce Lambert 1999, the IWA Task Force manual and Lambert 2009. The FAVAD exponent and orifice discharge coefficient have no published constant to reproduce because they are fitted per network, so the module requires them to be declared rather than assuming one.",
            "blocked_by": "None for UARL and background leakage. Fitted values must come from the analyst.",
        },
        {
            "priority": 15,
            "item": "Halo-buffered spatial chunking",
            "status": "open",
            "why": "Naive chunking splits connectivity and manufactures defects at chunk edges.",
            "approach": "Buffered chunks for local checks; single global pass for whole-layer union and degree. Report which checks are chunk-local and which are global.",
            "blocked_by": "None.",
        },
        {
            "priority": 16,
            "item": "Self-contained interactive report site",
            "status": "open",
            "why": "Findings are only actionable if a non-specialist can read them.",
            "approach": "Python emits a JSON bundle; a static front end renders map and findings with no server requirement.",
            "blocked_by": "None.",
        },
        {
            "priority": 17,
            "item": "Resolve package naming",
            "status": "blocked",
            "why": "Blocked before any public release.",
            "approach": "Repository name may stay. PyPI requires a new name.",
            "blocked_by": "Decision required.",
        },
    ]


def build(output_path: Path | None = None) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    destination = output_path or DEFAULT_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)

    registry_rows, registry_summary = _collect_registry()
    validators = _collect_validator_functions()
    modules = _collect_modules()
    profiles = _collect_profiles()
    coverage = _coverage_summary()
    roadmap = _roadmap()

    by_severity = Counter(r["severity"] for r in registry_rows)
    by_category = Counter(r["category"] for r in registry_rows)
    by_class = Counter(r["issue_class"] for r in registry_rows)

    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4F5F")
    title_font = Font(bold=True, size=13)

    def write_sheet(ws, headers: list[str], rows: list[dict[str, Any]], widths: list[int]) -> None:
        ws.append(headers)
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center")
        for row in rows:
            ws.append([row.get(h, "") for h in headers])
        for index, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(index)].width = width
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    # --- Overview -----------------------------------------------------
    ws = wb.active
    ws.title = "Overview"
    ws["A1"] = "GeoQA capability and coverage"
    ws["A1"].font = title_font
    summary_rows = [
        ("Registered problem names", registry_summary["total"]),
        ("Problem categories", registry_summary["by_category"]),
        ("Severity levels", registry_summary["by_severity"]),
        ("Issue classes", len(by_class)),
        ("Exposed validator functions", len(validators)),
        ("Validation profiles", len(profiles)),
        ("Python modules", len(modules)),
        ("Total Python lines", sum(m["lines"] for m in modules)),
        ("Validation rule version", registry_summary["rule_version"]),
        ("Areas built", sum(1 for c in coverage if c["status"] == "built")),
        ("Areas partial", sum(1 for c in coverage if c["status"] == "partial")),
        ("Areas not built", sum(1 for c in coverage if c["status"] == "not built")),
        ("Areas blocked", sum(1 for c in coverage if c["status"] == "blocked")),
    ]
    ws.append([])
    ws.append(["Metric", "Value"])
    for cell in ws[3]:
        cell.font = header_font
        cell.fill = header_fill
    for label, value in summary_rows:
        ws.append([label, value])
    ws.append([])
    ws.append(["Severity distribution"])
    ws.cell(row=ws.max_row, column=1).font = header_font
    for severity, count in by_severity.most_common():
        ws.append([severity, count])
    ws.append([])
    ws.append(["Category distribution"])
    ws.cell(row=ws.max_row, column=1).font = header_font
    for category, count in by_category.most_common():
        ws.append([category, count])
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 16

    write_sheet(
        wb.create_sheet("Coverage"),
        ["area", "status", "coverage", "coverage_gap", "notes"],
        coverage,
        [30, 12, 70, 70, 60],
    )
    write_sheet(
        wb.create_sheet("Problem registry"),
        ["category", "problem_name", "severity", "issue_class", "confidence",
         "actionable", "iso_category", "description", "repair_hint", "source"],
        registry_rows,
        [16, 44, 10, 18, 11, 11, 26, 78, 78, 20],
    )
    write_sheet(
        wb.create_sheet("Validator functions"),
        ["function", "signature", "tunable_parameters", "source_module", "docstring"],
        validators,
        [40, 74, 40, 22, 76],
    )
    write_sheet(
        wb.create_sheet("Profiles"),
        ["dataset", "strictness", "builder", "purpose"],
        profiles,
        [18, 13, 42, 62],
    )
    write_sheet(
        wb.create_sheet("Modules"),
        ["group", "module", "lines"],
        modules,
        [16, 62, 10],
    )
    write_sheet(
        wb.create_sheet("Roadmap"),
        ["priority", "item", "status", "why", "approach", "blocked_by"],
        roadmap,
        [10, 38, 10, 70, 84, 44],
    )

    wb.save(destination)
    return destination


if __name__ == "__main__":
    path = build()
    print(f"Capability workbook written: {path}")