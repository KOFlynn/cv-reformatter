"""The PII canaries the log tests seed into Candidate c04, shared by the
writer's tests (``tests/runlog/``) and the API's (``tests/api/``)."""

from cvr.golden import CANDIDATES_DIR, load_candidate

CANARY_EMAIL = "Canary-7F3@example.invalid"
CANARY_PHONE = "+44 7391 658 204"
CANARY_ADDRESS = "17 Zebulon Quay"
CANARIES = (CANARY_EMAIL, CANARY_PHONE, CANARY_ADDRESS)


def canary_document(layout):
    """Candidate c04 with its email, phone and first address line replaced by
    canaries, rendered through ``layout``; built here, nothing in the fixtures
    changes."""
    base = load_candidate(CANDIDATES_DIR / "c04.json")
    pii = base.pii.model_copy(
        update={
            "email": CANARY_EMAIL,
            "phone": CANARY_PHONE,
            "address": [CANARY_ADDRESS, *base.pii.address[1:]],
        }
    )
    candidate = base.model_copy(update={"pii": pii})
    generated = layout.generate(candidate)
    return candidate, generated.manifest, generated.document
