from dataclasses import dataclass, asdict
from typing import Optional, Any
import json


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
    session_id: Optional[str] = None

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

    def validate(self) -> list[str]:
        """Validate context and return list of errors."""
        errors = []
        if not self.crop:
            errors.append("Missing required field: crop")
        if not self.country:
            errors.append("Missing required field: country")
        return errors

    def merge(self, other: "FarmerContext") -> "FarmerContext":
        """Merge another context into this one, with other taking precedence for non-None values."""
        new_data = asdict(self)
        other_data = asdict(other)
        for key, value in other_data.items():
            if value is not None:
                new_data[key] = value
        return FarmerContext(**new_data)

    def to_json(self) -> str:
        """Serialize context to JSON."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "FarmerContext":
        """Deserialize context from JSON."""
        data = json.loads(json_str)
        return cls(**data)
