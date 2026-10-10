from __future__ import annotations

import argparse
import json

from geoqa.profile_registry import get_geoqa_profile, list_geoqa_profiles


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("profiles", help="List or inspect GeoQA profiles.")
    profile_subparsers = parser.add_subparsers(dest="profiles_command", required=True)

    list_parser = profile_subparsers.add_parser("list", help="List available profiles.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.set_defaults(handler=run_list)

    show_parser = profile_subparsers.add_parser("show", help="Show a single profile.")
    show_parser.add_argument("name", help="Profile name.")
    show_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    show_parser.set_defaults(handler=run_show)


def run_list(args: argparse.Namespace) -> int:
    profiles = list_geoqa_profiles()
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": profile.name,
                        "maturity": profile.maturity,
                        "description": profile.description,
                    }
                    for profile in profiles
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    print("Available profiles:")
    for profile in profiles:
        print(f"- {profile.name} [{profile.maturity}] {profile.description}")
    return 0


def run_show(args: argparse.Namespace) -> int:
    profile = get_geoqa_profile(args.name)
    if profile is None:
        print(f"Unknown profile: {args.name}")
        return 1
    payload = {
        "name": profile.name,
        "description": profile.description,
        "maturity": profile.maturity,
        "severity_overrides": profile.severity_overrides,
        "downgrade_rules": profile.downgrade_rules,
        "suppression_rules": profile.suppression_rules,
        "suppressed_problems": list(profile.suppressed_problems),
        "problem_policies": profile.problem_policies,
        "families": [
            {
                "dataset_type": family.dataset_type,
                "enabled_validators": list(family.enabled_validators),
                "disabled_validators": list(family.disabled_validators),
                "validator_options": family.validator_options,
                "has_context_builder": family.context_builder is not None,
            }
            for family in profile.families
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Profile: {profile.name}")
    print(f"Maturity: {profile.maturity}")
    print(f"Description: {profile.description}")
    print("Families:")
    for family in payload["families"]:
        print(
            f"- {family['dataset_type']}: "
            f"{', '.join(family['enabled_validators']) or 'none'}"
        )
    if payload["suppressed_problems"]:
        print(f"Suppressed problems: {', '.join(payload['suppressed_problems'])}")
    if payload["downgrade_rules"]:
        print("Downgrades:")
        for name, severity in sorted(payload["downgrade_rules"].items()):
            print(f"- {name} -> {severity}")
    if payload["suppression_rules"]:
        print("Suppression rules:")
        for name, rule in sorted(payload["suppression_rules"].items()):
            print(f"- {name}: {rule}")
    return 0


__all__ = ["configure_parser"]
