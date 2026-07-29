"""Input validation. Fails loudly rather than letting a unit error propagate.

Run on every table before it touches the model. The failure mode this guards
against is a collaborator renaming a column or switching kg for tonnes without
telling anyone, which otherwise produces a plausible-looking result that is
wrong by three orders of magnitude.
"""

import pandas as pd

from ..config import regulatory_constants as rc

VALID_CORRIDORS = set(rc.CORRIDORS)
VALID_PRODUCTS = set(rc.PRODUCTS)


class ContractViolation(AssertionError):
    """An input table does not match the agreed data contract."""


def _require_columns(df: pd.DataFrame, required: set, table: str, owner: str):
    missing = required - set(df.columns)
    if missing:
        raise ContractViolation(
            f"{table} is missing required columns: {sorted(missing)}. "
            f"Agreed schema is in the build spec. Raise with {owner}."
        )


def _require_labels(df: pd.DataFrame, column: str, allowed: set, table: str, owner: str):
    found = set(df[column].unique())
    unexpected = found - allowed
    if unexpected:
        raise ContractViolation(
            f"{table} has unexpected {column} labels: {sorted(unexpected)}. "
            f"Expected only {sorted(allowed)}. Label mismatch breaks the join "
            f"silently. Raise with {owner}."
        )


def validate_emissions_table(df: pd.DataFrame) -> pd.DataFrame:
    """Validate Riya's emissions_table.csv."""
    owner = "Riya (Student 1)"
    _require_columns(
        df,
        {
            "corridor",
            "product",
            "pathway",
            "embedded_emissions_tco2e_per_tonne",
            "origin_carbon_price_eur_per_tco2e",
            "source",
        },
        "emissions_table.csv",
        owner,
    )
    _require_labels(df, "corridor", VALID_CORRIDORS, "emissions_table.csv", owner)
    _require_labels(df, "product", VALID_PRODUCTS, "emissions_table.csv", owner)

    col = "embedded_emissions_tco2e_per_tonne"
    if df[col].max() >= 50:
        raise ContractViolation(
            f"{col} has a maximum of {df[col].max():.1f}, which is too high for "
            f"tCO2e per tonne of product. Grey hydrogen at 9-12 kgCO2/kg is 9-12 "
            f"tCO2e/t; brown ammonia tops out around 9. A value of 50 or more "
            f"suggests the column is in kgCO2e. Confirm units with {owner}."
        )
    if (df[col] < 0).any():
        raise ContractViolation(f"{col} contains negative values. Check with {owner}.")

    if (df["origin_carbon_price_eur_per_tco2e"] < 0).any():
        raise ContractViolation(
            f"origin_carbon_price_eur_per_tco2e contains negative values. "
            f"Use 0 where no carbon price is paid at origin. Check with {owner}."
        )

    dupes = df.duplicated(subset=["corridor", "product", "pathway"])
    if dupes.any():
        raise ContractViolation(
            f"emissions_table.csv has duplicate corridor/product/pathway rows: "
            f"{df[dupes][['corridor', 'product', 'pathway']].to_dict('records')}. "
            f"Check with {owner}."
        )
    return df


def validate_logistics_table(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the corridor logistics table derived from Gayu's notebooks."""
    owner = "Gayu (Student 2)"
    _require_columns(
        df,
        {
            "corridor",
            "vessel_class",
            "route_scenario",
            "distance_nm",
            "fuel_consumption_t_per_nm",
            "voyage_fuel_total_t",
            "voyage_co2_t",
            "port_in_port_emissions_t",
            "voyage_energy_mj",
            "fueleu_actual_intensity_gco2e_mj",
        },
        "corridor_logistics.csv",
        owner,
    )
    _require_labels(df, "corridor", VALID_CORRIDORS, "corridor_logistics.csv", owner)

    # Gayu's SeaRoute distances are 2,962 nm and 10,403 nm, so the old
    # "under 1,000 means kilometres" heuristic still holds, but the upper
    # sanity bound matters too now that the Atlantic corridor is much shorter
    # than the build spec assumed.
    if df["distance_nm"].min() <= 1000:
        raise ContractViolation(
            f"distance_nm minimum is {df['distance_nm'].min():.0f}. Gayu's SeaRoute "
            f"figures are 2,962 nm for Halifax-Hamburg and 10,403 nm for "
            f"Ningbo-Felixstowe, so anything under 1,000 suggests kilometres or a "
            f"partial leg. Confirm units with {owner}."
        )
    if df["distance_nm"].max() > 20_000:
        raise ContractViolation(
            f"distance_nm maximum is {df['distance_nm'].max():.0f}, which exceeds "
            f"the Cape of Good Hope routing of 14,815 nm. Check with {owner}."
        )

    # Internal consistency: voyage_fuel_total_t should equal distance x rate.
    implied = df["distance_nm"] * df["fuel_consumption_t_per_nm"]
    drift = (implied - df["voyage_fuel_total_t"]).abs() / df["voyage_fuel_total_t"]
    if (drift > 0.01).any():
        bad = df.loc[drift > 0.01, "corridor"].tolist()
        raise ContractViolation(
            f"voyage_fuel_total_t does not match distance_nm x fuel_consumption_t_per_nm "
            f"for: {bad}. One of the three columns is inconsistent. Check with {owner}."
        )

    if (df["port_in_port_emissions_t"] >= df["voyage_co2_t"]).any():
        raise ContractViolation(
            "port_in_port_emissions_t is greater than or equal to voyage_co2_t. "
            "Berth and hotelling emissions should be a small fraction of a "
            f"multi-thousand-mile voyage. Check with {owner}."
        )

    intensity = df["fueleu_actual_intensity_gco2e_mj"]
    if not intensity.between(0, 150).all():
        raise ContractViolation(
            f"fueleu_actual_intensity_gco2e_mj is outside 0-150. The 2020 fleet "
            f"average is {rc.FUELEU_BASELINE_2020} gCO2e/MJ, so realistic values sit "
            f"roughly between 20 and 100. Check with {owner}."
        )
    return df


def validate_commercial_table(df: pd.DataFrame) -> pd.DataFrame:
    """Validate commercial_inputs.csv.

    This table has no owner assigned in the build spec. See the note in
    data/README.md: production, conversion and shipping costs are three of the
    six terms in total_delivered_cost, but neither Riya's nor Gayu's contract
    covers them.
    """
    owner = "UNASSIGNED, see data/README.md"
    _require_columns(
        df,
        {
            "corridor",
            "product",
            "pathway",
            "production_cost_eur_per_tonne",
            "conversion_cost_eur_per_tonne",
            "shipping_cost_eur_per_tonne",
            "source",
        },
        "commercial_inputs.csv",
        owner,
    )
    _require_labels(df, "corridor", VALID_CORRIDORS, "commercial_inputs.csv", owner)
    _require_labels(df, "product", VALID_PRODUCTS, "commercial_inputs.csv", owner)

    for col in (
        "production_cost_eur_per_tonne",
        "conversion_cost_eur_per_tonne",
        "shipping_cost_eur_per_tonne",
    ):
        if (df[col] < 0).any():
            raise ContractViolation(f"{col} contains negative values. Check with {owner}.")
    return df


def validate_join(emissions: pd.DataFrame, logistics: pd.DataFrame, commercial: pd.DataFrame):
    """Check the three tables actually join before the runner tries to use them."""
    e_keys = set(zip(emissions["corridor"], emissions["product"], emissions["pathway"]))
    c_keys = set(zip(commercial["corridor"], commercial["product"], commercial["pathway"]))

    orphan_emissions = e_keys - c_keys
    if orphan_emissions:
        raise ContractViolation(
            f"{len(orphan_emissions)} corridor/product/pathway combinations appear in "
            f"emissions_table.csv but not commercial_inputs.csv, for example "
            f"{sorted(orphan_emissions)[:3]}. Every pathway needs a cost."
        )

    missing_logistics = set(emissions["corridor"]) - set(logistics["corridor"])
    if missing_logistics:
        raise ContractViolation(
            f"No logistics row for corridor(s): {sorted(missing_logistics)}."
        )
