Water network pack

This pack configures GeoQA for pipe and utility-network style line datasets.

It does not implement validator logic itself. Instead it provides:
- schema detection
- threshold defaults
- profile definitions
- severity, confidence, actionable, and suppression policies

Profiles:
- water_network_quick
- water_network_strict
- water_network_audit

The default `water_network` profile aliases the strict profile for backward compatibility.
