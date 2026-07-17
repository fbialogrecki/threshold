import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from users.domain.models import SecretLocationKeyEnvelope, SecretLocationPayload
from users.domain.secret_locations import serialize_secret_location_for_viewer

EXACT_ADDRESS = "Jasna 1, Warsaw"
CIPHERTEXT = "ciphertext:v1:not-the-address"
RECIPIENT_KEY = "sealed-key-for-approved-user"
OTHER_RECIPIENT_KEY = "sealed-key-for-other-user"


def test_secret_location_storage_has_no_plaintext_exact_address(session: Session) -> None:
    payload = SecretLocationPayload(
        event_id="event-1",
        city="Warsaw",
        area="Centrum",
        encrypted_payload_ciphertext=CIPHERTEXT,
        encrypted_payload_nonce="nonce-v1",
        crypto_suite="xchacha20poly1305+sealedbox-v1",
        payload_version=1,
    )
    session.add(payload)
    session.commit()

    row = session.scalar(
        select(SecretLocationPayload).where(SecretLocationPayload.event_id == "event-1")
    )

    assert row is not None
    stored = json.dumps(
        {
            column.name: getattr(row, column.name)
            for column in SecretLocationPayload.__table__.columns
        },
        default=str,
    )
    assert EXACT_ADDRESS not in stored
    assert "exact_address" not in SecretLocationPayload.__table__.columns
    assert "plaintext_address" not in SecretLocationPayload.__table__.columns


def test_unauthorized_secret_location_response_hides_plaintext_and_keys(
    session: Session,
) -> None:
    payload = SecretLocationPayload(
        event_id="event-2",
        city="Warsaw",
        area="Praga",
        encrypted_payload_ciphertext=CIPHERTEXT,
        encrypted_payload_nonce="nonce-v1",
        crypto_suite="xchacha20poly1305+sealedbox-v1",
        payload_version=1,
    )
    payload.key_envelopes = [
        SecretLocationKeyEnvelope(
            recipient_user_id="approved-user",
            encrypted_payload_key=RECIPIENT_KEY,
            key_version=1,
        )
    ]
    session.add(payload)
    session.commit()
    session.refresh(payload)

    response = serialize_secret_location_for_viewer(
        payload,
        viewer_user_id="unauthorized-user",
        reveal_allowed=True,
    )

    response_json = response.model_dump_json()
    assert EXACT_ADDRESS not in response_json
    assert RECIPIENT_KEY not in response_json
    assert response.encrypted_payload is None
    assert response.key_envelope is None
    assert response.city == "Warsaw"
    assert response.area == "Praga"


def test_revealed_authorized_response_returns_only_own_encrypted_material(session: Session) -> None:
    payload = SecretLocationPayload(
        event_id="event-3",
        city="Warsaw",
        area="Wola",
        encrypted_payload_ciphertext=CIPHERTEXT,
        encrypted_payload_nonce="nonce-v1",
        crypto_suite="xchacha20poly1305+sealedbox-v1",
        payload_version=1,
    )
    payload.key_envelopes = [
        SecretLocationKeyEnvelope(
            recipient_user_id="approved-user",
            encrypted_payload_key=RECIPIENT_KEY,
            key_version=1,
        ),
        SecretLocationKeyEnvelope(
            recipient_user_id="other-user",
            encrypted_payload_key=OTHER_RECIPIENT_KEY,
            key_version=1,
        ),
    ]
    session.add(payload)
    session.commit()
    session.refresh(payload)

    response = serialize_secret_location_for_viewer(
        payload,
        viewer_user_id="approved-user",
        reveal_allowed=True,
    )

    response_json = response.model_dump_json()
    assert EXACT_ADDRESS not in response_json
    assert response.encrypted_payload is not None
    assert response.encrypted_payload.ciphertext == CIPHERTEXT
    assert response.key_envelope is not None
    assert response.key_envelope.encrypted_payload_key == RECIPIENT_KEY
    assert OTHER_RECIPIENT_KEY not in response_json
