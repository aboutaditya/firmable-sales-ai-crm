"""Company profile model and its checkpoint state serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sales_intelligence.scoring import SCORE_VERSION

_CHECKPOINT_SETS = (
    "_ips",
    "_domains",
    "_vulnerabilities",
    "_critical_vulnerabilities",
    "_eol_products",
)


@dataclass
class CompanyProfile:
    company_id: str
    domain: str
    organization: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    asset_count: int = 0
    unique_ip_count: int = 0
    unique_domain_count: int = 0
    vulnerability_count: int = 0
    critical_vulnerability_count: int = 0
    eol_product_count: int = 0
    exposed_rdp: bool = False
    exposed_database: bool = False
    exposed_exchange: bool = False
    security_tag_count: int = 0
    security_score: int = 0
    score_version: str = SCORE_VERSION
    _ips: set[str] = field(default_factory=set, repr=False)
    _domains: set[str] = field(default_factory=set, repr=False)
    _vulnerabilities: set[str] = field(default_factory=set, repr=False)
    _critical_vulnerabilities: set[str] = field(default_factory=set, repr=False)
    _eol_products: set[str] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict:
        result = asdict(self)
        for internal in _CHECKPOINT_SETS:
            result.pop(internal, None)
        return result

    def to_state(self) -> dict:
        """Serialize the profile for checkpoint storage, including private sets."""
        state = self.to_dict()
        state.update({key: sorted(getattr(self, key)) for key in _CHECKPOINT_SETS})
        return state

    @classmethod
    def from_state(cls, state: dict) -> "CompanyProfile":
        """Rebuild a profile from a checkpoint state dict."""
        state = dict(state)
        private_sets = {
            key: set(state.pop(key, [])) for key in _CHECKPOINT_SETS
        }
        fields = {
            key: value
            for key, value in state.items()
            if key in cls.__dataclass_fields__ and not key.startswith("_")
        }
        profile = cls(**fields)
        for key, value in private_sets.items():
            setattr(profile, key, value)
        return profile