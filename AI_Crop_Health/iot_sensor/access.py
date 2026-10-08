"""
Who may see and register IoT hardware.

Two problems this module exists to solve:

1. Every view originally filtered `Field.objects.filter(owner=request.user)`,
   so a farmer leasing land saw an empty dashboard forever.
2. Hardware registration must be gated. A farmer qualifies either by passing
   farmer verification (government ID + address proof + selfie - NOT ownership
   proof, which a farmer cannot produce) or by holding an approved lease on
   real land. Land owners qualify by owner verification.
"""

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)

# A lease only counts once it is fully approved. 'owner_approved' is still
# awaiting admin review, so it must NOT grant field access.
ACTIVE_LEASE_STATUSES = ('approved', 'completed')


def get_profile(user):
    """
    Return the user's AgroProfile, or None.

    The related_name is `agroprofile`; code reading `user.agro_profile` always
    raised AttributeError and silently treated everyone as unverified.
    """
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'agroprofile', None)


def leased_land_ids(user):
    """Primary keys of Land this user farms under an approved lease."""
    profile_user = user if user and user.is_authenticated else None
    if profile_user is None:
        return []
    from agrolease.models import LeaseRequest
    return list(
        LeaseRequest.objects
        .filter(farmer=profile_user, status__in=ACTIVE_LEASE_STATUSES)
        .values_list('land_id', flat=True)
    )


def visible_fields(user):
    """
    Fields this user may view: ones they own, plus ones linked to land they
    lease under an approved lease. Returns an unevaluated queryset.
    """
    from .models import Field
    if not user or not user.is_authenticated:
        return Field.objects.none()

    criteria = Q(owner=user)
    land_ids = leased_land_ids(user)
    if land_ids:
        criteria |= Q(land_id__in=land_ids)
    return Field.objects.filter(criteria, is_active=True).distinct()


def can_manage_field(user, field):
    """
    True if the user may act on a field (irrigate, set thresholds).

    Owners of the field can. A farmer can only when the field is linked to land
    they hold an approved lease on - viewing is not the same as actuating a
    valve, but a leaseholder is the person actually farming it.
    """
    if not user or not user.is_authenticated or field is None:
        return False
    if field.owner_id == user.pk:
        return True
    return bool(field.land_id) and field.land_id in leased_land_ids(user)


def hardware_registration_state(user):
    """
    Decide whether this user may register hardware.

    Returns (allowed: bool, reason: str). The reason is shown to the user, so it
    says what to do next rather than just refusing.
    """
    profile = get_profile(user)
    if profile is None:
        return False, (
            'Complete your AgroLease profile before registering hardware.'
        )

    roles = profile.effective_roles()

    # Path 1: verified account (owner or farmer).
    if profile.is_verified:
        return True, ''

    # Path 2: farmer with an approved lease on real land.
    if 'farmer' in roles and leased_land_ids(user):
        return True, ''

    # Not allowed - explain which path is closest to complete.
    if profile.verification_status == 'pending':
        return False, (
            'Your verification documents are submitted and awaiting admin '
            'review. Hardware registration unlocks once approved.'
        )
    if profile.verification_status == 'rejected':
        reason = profile.rejection_reason or 'Your documents were not accepted.'
        return False, f'Verification was rejected: {reason} Please re-upload and resubmit.'

    missing = profile.missing_documents()
    if 'farmer' in roles and 'owner' not in roles:
        return False, (
            'To register hardware, either get verified (upload: '
            + ', '.join(missing) + ') or have an approved lease on land.'
        )
    return False, (
        'Get your account verified to register hardware. Still required: '
        + ', '.join(missing) + '.'
    )


def require_hardware_access(user):
    """Boolean-only form of hardware_registration_state."""
    allowed, _ = hardware_registration_state(user)
    return allowed
