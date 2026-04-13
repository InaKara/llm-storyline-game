"""Cross-file consistency checks that Pydantic alone cannot express."""

from __future__ import annotations

from backend.app.domain.scenario_models import ScenarioPackage


def validate_scenario_package(package: ScenarioPackage) -> list[str]:
    """Return a list of validation errors (empty list means valid).

    Checks cross-file references that single-file Pydantic validation
    cannot catch — for example, a gate referencing a claim that doesn't
    exist in the claims list.
    """
    errors: list[str] = []

    # Collect known IDs
    claim_ids = {c.id for c in package.logic.claims}
    character_ids = {c.id for c in package.characters.characters}
    location_ids = {loc.id for loc in package.locations.locations}

    # Gate claim references must exist
    for gate in package.logic.gates:
        for cid in gate.required_claim_ids:
            if cid not in claim_ids:
                errors.append(
                    f"Gate '{gate.id}' references unknown claim '{cid}'"
                )

    # Asset portrait keys must match character IDs
    for char_id in package.assets.portraits:
        if char_id not in character_ids:
            errors.append(
                f"Asset portraits reference unknown character '{char_id}'"
            )

    # Asset background keys must match location IDs
    for loc_id in package.assets.backgrounds:
        if loc_id not in location_ids:
            errors.append(
                f"Asset backgrounds reference unknown location '{loc_id}'"
            )

    # At least one gate must be defined
    if not package.logic.gates:
        errors.append("No gates defined — the game has no progression")

    # Starting location (from story or initial_state) must exist
    # We check that the first location marked as initially_available exists
    available_locations = [
        loc.id for loc in package.locations.locations if loc.initially_available
    ]
    if not available_locations:
        errors.append("No location is marked as initially_available")

    # initial_state.starting_location must be a known location
    if package.initial_state.starting_location not in location_ids:
        errors.append(
            f"initial_state.starting_location '{package.initial_state.starting_location}' "
            f"is not a known location"
        )

    # initial_state.starting_addressed_character must be a known character
    if package.initial_state.starting_addressed_character not in character_ids:
        errors.append(
            f"initial_state.starting_addressed_character "
            f"'{package.initial_state.starting_addressed_character}' "
            f"is not a known character"
        )

    # Embedded asset fields in characters must match the asset manifest
    for char in package.characters.characters:
        manifest_path = package.assets.portraits.get(char.id)
        if manifest_path is not None and not manifest_path.endswith(char.portrait_asset):
            errors.append(
                f"Character '{char.id}' portrait_asset '{char.portrait_asset}' "
                f"does not match manifest path '{manifest_path}'"
            )

    # Embedded asset fields in locations must match the asset manifest
    for loc in package.locations.locations:
        manifest_path = package.assets.backgrounds.get(loc.id)
        if manifest_path is not None and not manifest_path.endswith(loc.background_asset):
            errors.append(
                f"Location '{loc.id}' background_asset '{loc.background_asset}' "
                f"does not match manifest path '{manifest_path}'"
            )

    # End condition location references must exist
    for ec in package.logic.end_conditions:
        if ec.location and ec.location not in location_ids:
            errors.append(
                f"End condition references unknown location '{ec.location}'"
            )

    return errors
