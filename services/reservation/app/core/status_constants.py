RENT_FINAL_STATUS_CODES = (
    "cancelled",
    "fullfilled",
    "rejected_not_received",
    "rejected_invalid_proof",
    "rejected_amount_low",
    "rejected_amount_high",
    "rejected_wrong_destination",
    "expired_no_proof",
    "expired_slot_unavailable",
    "dispute_resolved",
)

RENT_PENDING_PAYMENT_STATUS_CODE = "pending_payment"
RENT_UNDER_REVIEW_STATUS_CODE = "under_review"

RENT_HOLD_STATUS_CODES = (
    RENT_PENDING_PAYMENT_STATUS_CODE,
    "pending_proof",
    "proof_submitted",
    RENT_UNDER_REVIEW_STATUS_CODE,
    "needs_info",
)

SCHEDULE_AVAILABLE_STATUS_CODE = "available"
SCHEDULE_EXPIRED_STATUS_CODE = "expired"
SCHEDULE_PENDING_STATUS_CODE = "pending"
SCHEDULE_HOLD_PAYMENT_STATUS_CODE = "hold_payment"
SCHEDULE_BLOCKED_ADMIN_STATUS_CODE = "blocked_admin"

SCHEDULE_BLOCKING_STATUS_CODES = (
    SCHEDULE_PENDING_STATUS_CODE,
    SCHEDULE_HOLD_PAYMENT_STATUS_CODE,
    SCHEDULE_BLOCKED_ADMIN_STATUS_CODE,
)

SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES = (SCHEDULE_EXPIRED_STATUS_CODE,)
