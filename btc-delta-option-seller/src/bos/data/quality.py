from enum import StrEnum


class DataQuality(StrEnum):
    EXACT = "EXACT"
    RECONSTRUCTED = "RECONSTRUCTED"
    ESTIMATED = "ESTIMATED"
