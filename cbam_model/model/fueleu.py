"""FuelEU Maritime penalty. Halifax-Hamburg only.

Felixstowe is outside EU jurisdiction, so Ningbo-Felixstowe carries no FuelEU
cost at all. That is a real cost difference between the corridors and is
reported as such, not treated as missing data.
"""


from ..config import regulatory_constants as rc


def compliance_balance_gco2e(
    actual_intensity_gco2e_mj: float,
    target_intensity_gco2e_mj: float,
    energy_consumed_mj: float,
) -> float:
    """Annex IV Part A compliance balance, in gCO2e.

    Positive means over-compliance (a surplus), negative means a deficit.
    """
    return (target_intensity_gco2e_mj - actual_intensity_gco2e_mj) * energy_consumed_mj


def fueleu_cost(
    actual_intensity_gco2e_mj: float,
    energy_consumed_mj: float,
    year: int,
    target_intensity_gco2e_mj: float | None = None,
    consecutive_deficit_periods: int = 1,
) -> float:
    """FuelEU Maritime penalty in EUR.

    Annex IV Part B:

        penalty = |compliance balance| / (GHGIE_actual x 41 000) x 2 400

    The division by GHGIE_actual is what converts a gCO2e deficit into tonnes of
    VLSFO energy equivalent, which is the unit the EUR 2,400 rate is expressed
    in.

    The build spec omitted that divisor, writing the penalty as
    `deficit x energy / 41000 x 2400`. Since GHGIE_actual sits around
    90 gCO2e/MJ, the spec version overstates the penalty by roughly ninety
    times. Verified against Annex IV Part B before implementing this.

    Args:
        consecutive_deficit_periods: n in the Annex IV Part B multiplier
            1 + (n - 1) / 10, applied where a ship has run a deficit for two or
            more consecutive reporting periods. Defaults to 1, meaning no
            escalation.
    """
    if target_intensity_gco2e_mj is None:
        target_intensity_gco2e_mj = rc.fueleu_target(year)

    balance = compliance_balance_gco2e(
        actual_intensity_gco2e_mj, target_intensity_gco2e_mj, energy_consumed_mj
    )

    if balance >= 0:
        return 0.0  # compliant, or in surplus

    deficit_gco2e = abs(balance)
    vlsfo_tonnes_equivalent = deficit_gco2e / (
        actual_intensity_gco2e_mj * rc.VLSFO_MJ_PER_TONNE
    )
    penalty = vlsfo_tonnes_equivalent * rc.FUELEU_PENALTY_EUR_PER_TONNE_VLSFO

    if consecutive_deficit_periods > 1:
        penalty *= 1 + (consecutive_deficit_periods - 1) / 10

    return penalty


def effective_intensity_with_rfnbo(
    intensity_gco2e_mj: float, rfnbo_energy_share: float, year: int
) -> float:
    """Apply the Article 5 RFNBO reward factor.

    Energy from renewable fuels of non-biological origin, which is what green
    hydrogen and e-ammonia bunker fuel are, counts twice for the purposes of the
    GHG intensity calculation until the end of 2033. The effect is to lower the
    reported intensity, so it is modelled here as a reduction in the effective
    figure that goes into the penalty calculation.

    Args:
        rfnbo_energy_share: Fraction of on-board energy from RFNBO, 0 to 1.
    """
    if year > rc.FUELEU_RFNBO_MULTIPLIER_EXPIRES:
        return intensity_gco2e_mj
    if not 0.0 <= rfnbo_energy_share <= 1.0:
        raise ValueError(f"rfnbo_energy_share must be between 0 and 1, got {rfnbo_energy_share}")

    # Doubling the RFNBO energy in the denominator dilutes the fleet-average
    # intensity by that share.
    multiplier = rc.FUELEU_RFNBO_MULTIPLIER
    denominator = 1 + rfnbo_energy_share * (multiplier - 1)
    return intensity_gco2e_mj / denominator


def fueleu_applies(corridor: str) -> bool:
    return corridor in rc.FUELEU_APPLIES_TO
