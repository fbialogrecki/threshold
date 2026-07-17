from pydantic import BaseModel, ConfigDict
from users.domain.models import SecretLocationPayload


class EncryptedLocationPayloadResponse(BaseModel):
    ciphertext: str
    nonce: str
    crypto_suite: str
    payload_version: int


class SecretLocationKeyEnvelopeResponse(BaseModel):
    recipient_user_id: str
    encrypted_payload_key: str
    key_version: int


class SecretLocationViewerResponse(BaseModel):
    event_id: str
    city: str
    area: str | None
    encrypted_payload: EncryptedLocationPayloadResponse | None = None
    key_envelope: SecretLocationKeyEnvelopeResponse | None = None

    model_config = ConfigDict(from_attributes=True)


def serialize_secret_location_for_viewer(
    payload: SecretLocationPayload,
    *,
    viewer_user_id: str | None,
    reveal_allowed: bool,
) -> SecretLocationViewerResponse:
    key_envelope = None
    if viewer_user_id is not None and reveal_allowed:
        key_envelope = next(
            (
                envelope
                for envelope in payload.key_envelopes
                if envelope.recipient_user_id == viewer_user_id
            ),
            None,
        )

    if key_envelope is None:
        return SecretLocationViewerResponse(
            event_id=payload.event_id,
            city=payload.city,
            area=payload.area,
        )

    return SecretLocationViewerResponse(
        event_id=payload.event_id,
        city=payload.city,
        area=payload.area,
        encrypted_payload=EncryptedLocationPayloadResponse(
            ciphertext=payload.encrypted_payload_ciphertext,
            nonce=payload.encrypted_payload_nonce,
            crypto_suite=payload.crypto_suite,
            payload_version=payload.payload_version,
        ),
        key_envelope=SecretLocationKeyEnvelopeResponse(
            recipient_user_id=key_envelope.recipient_user_id,
            encrypted_payload_key=key_envelope.encrypted_payload_key,
            key_version=key_envelope.key_version,
        ),
    )
