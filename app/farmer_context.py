from dataclasses import dataclass
from typing import Optional


@dataclass
class FarmerContext:
    crop: str
    country: str
    province: Optional[str] = None
    district: Optional[str] = None
    previous_crop: Optional[str] = None
    soil_type: Optional[str] = None
    irrigation: Optional[str] = None
    sowing_date: Optional[str] = None
    growth_stage: Optional[str] = None
    problem: Optional[str] = None

    def to_prompt(self) -> str:
        fields = [
            ("Crop", self.crop),
            ("Country", self.country),
            ("Province", self.province),
            ("District", self.district),
            ("Previous crop", self.previous_crop),
            ("Soil type", self.soil_type),
            ("Irrigation", self.irrigation),
            ("Sowing date", self.sowing_date),
            ("Growth stage", self.growth_stage),
            ("Current problem", self.problem),
        ]
        lines = [
            f"- {name}: {value}"
            for name, value in fields
            if value
        ]
        return "FARMER CONTEXT:\n" + "\n".join(lines)
