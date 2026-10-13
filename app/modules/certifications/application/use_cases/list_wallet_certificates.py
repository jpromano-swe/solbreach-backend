from __future__ import annotations

from datetime import UTC
from typing import Any

from app.modules.certifications.domain.certificate_definitions import (
    CERTIFICATE_DEFINITIONS,
    CERTIFICATE_ORDER,
    LEGACY_CERTIFICATION_SLUGS,
    CertificateDefinition,
    absolute_certificate_url,
)
from app.modules.certifications.domain.entities.certification import (
    Certification,
    CertificationMintStatus,
)
from app.modules.certifications.domain.repositories.certification_repository import (
    CertificationRepository,
)
from app.modules.users.domain.entities.user import User


class ListWalletCertificatesUseCase:
    def __init__(self, certifications: CertificationRepository, public_base_url: str) -> None:
        self._certifications = certifications
        self._public_base_url = public_base_url

    async def execute(self, user: User) -> dict[str, Any]:
        records = await self._certifications.list_all_for_user(user.id)
        records_by_certificate_id = _records_by_certificate_id(records)
        certificates = [
            _certificate_payload(
                CERTIFICATE_DEFINITIONS[certificate_id],
                records_by_certificate_id.get(certificate_id),
                self._public_base_url,
            )
            for certificate_id in CERTIFICATE_ORDER
        ]
        minted_count = sum(1 for certificate in certificates if certificate["minted"])
        return {
            "walletAddress": user.wallet_address,
            "certificates": certificates,
            "summary": {
                "minted": minted_count,
                "total": len(CERTIFICATE_ORDER),
            },
        }


def _records_by_certificate_id(records: list[Certification]) -> dict[str, Certification]:
    mapped: dict[str, Certification] = {}
    for record in records:
        certificate_id = _certificate_id_for_record(record)
        if certificate_id is None:
            continue
        if certificate_id not in mapped or _record_rank(record) > _record_rank(mapped[certificate_id]):
            mapped[certificate_id] = record
    return mapped


def _certificate_id_for_record(record: Certification) -> str | None:
    if record.slug in CERTIFICATE_DEFINITIONS:
        return record.slug
    metadata_id = record.metadata.get("certificate_id") or record.metadata.get("certificateId")
    if isinstance(metadata_id, str) and metadata_id in CERTIFICATE_DEFINITIONS:
        return metadata_id
    legacy_id = LEGACY_CERTIFICATION_SLUGS.get(record.slug)
    if legacy_id is not None:
        return legacy_id
    completed_order = record.metadata.get("completed_level_order") or record.metadata.get("level")
    if completed_order in (1, "1"):
        return "solbreach-level-1"
    if completed_order in (2, "2"):
        return "solbreach-level-2"
    if completed_order in (3, "3"):
        return "solbreach-level-3"
    return None


def _record_rank(record: Certification) -> int:
    if record.mint_status == CertificationMintStatus.MINTED:
        return 3
    if record.slug in CERTIFICATE_DEFINITIONS:
        return 2
    return 1


def _certificate_payload(
    definition: CertificateDefinition,
    record: Certification | None,
    public_base_url: str,
) -> dict[str, Any]:
    image_uri = absolute_certificate_url(public_base_url, definition.image_path)
    metadata_uri = (
        _first_string(record, "metadata_uri", "metadataUri")
        if record is not None
        else None
    ) or absolute_certificate_url(public_base_url, definition.metadata_path)
    minted = record is not None and record.mint_status == CertificationMintStatus.MINTED
    status = "minted" if minted else "unlocked" if record is not None else "locked"
    return {
        "certificateId": definition.certificate_id,
        "certificateNumber": definition.certificate_number,
        "level": definition.level,
        "title": definition.title,
        "status": status,
        "minted": minted,
        "mintedAt": _datetime_string(record.minted_at) if record is not None else None,
        "assetId": _first_string(record, "asset_id", "assetId") if record is not None else None,
        "certificatePda": (
            _first_string(record, "certificate_pda", "certificatePda") if record is not None else None
        ),
        "metadataUri": metadata_uri,
        "imageUri": image_uri,
    }


def _first_string(record: Certification, snake_key: str, camel_key: str) -> str | None:
    direct_value = getattr(record, snake_key)
    if isinstance(direct_value, str) and direct_value:
        return direct_value
    for value in (record.metadata.get(snake_key), record.metadata.get(camel_key)):
        if isinstance(value, str) and value:
            return value
    return None


def _datetime_string(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")
