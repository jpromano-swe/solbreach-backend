from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CertificateDefinition:
    certificate_id: str
    certificate_number: int
    level: int
    title: str
    description: str
    image_path: str
    metadata_path: str


LEVEL_1_CERTIFICATE_ID = "solbreach-level-1"
LEVEL_2_CERTIFICATE_ID = "solbreach-level-2"
LEVEL_3_CERTIFICATE_ID = "solbreach-level-3"

CERTIFICATE_DEFINITIONS: dict[str, CertificateDefinition] = {
    LEVEL_1_CERTIFICATE_ID: CertificateDefinition(
        certificate_id=LEVEL_1_CERTIFICATE_ID,
        certificate_number=1,
        level=1,
        title="The Illusionist",
        description="Certificate awarded for completing SolBreach Level 1: The Illusionist.",
        image_path="/certificates/level-1.png",
        metadata_path="/certificates/metadata/level-1.json",
    ),
    LEVEL_2_CERTIFICATE_ID: CertificateDefinition(
        certificate_id=LEVEL_2_CERTIFICATE_ID,
        certificate_number=2,
        level=2,
        title="The Identity Thief",
        description="Certificate awarded for completing SolBreach Level 2: The Identity Thief.",
        image_path="/certificates/level-2.png",
        metadata_path="/certificates/metadata/level-2.json",
    ),
    LEVEL_3_CERTIFICATE_ID: CertificateDefinition(
        certificate_id=LEVEL_3_CERTIFICATE_ID,
        certificate_number=3,
        level=3,
        title="The Trojan Horse",
        description="Certificate awarded for completing SolBreach Level 3: The Trojan Horse.",
        image_path="/certificates/level-3.png",
        metadata_path="/certificates/metadata/level-3.json",
    ),
}

CERTIFICATE_ORDER = [
    LEVEL_1_CERTIFICATE_ID,
    LEVEL_2_CERTIFICATE_ID,
    LEVEL_3_CERTIFICATE_ID,
]

LEVEL_ORDER_TO_CERTIFICATE_ID = {
    1: LEVEL_1_CERTIFICATE_ID,
    2: LEVEL_2_CERTIFICATE_ID,
    3: LEVEL_3_CERTIFICATE_ID,
}

LEGACY_CERTIFICATION_SLUGS = {
    "static-pda-commander-hijack": LEVEL_2_CERTIFICATE_ID,
    "arbitrary-cpi-delegated-signer-abuse": LEVEL_3_CERTIFICATE_ID,
}


def absolute_certificate_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
