from rest_framework.throttling import UserRateThrottle


class EventListRateThrottle(UserRateThrottle):
    """
    Limits how often a single user can page through the domain event log —
    prevents scraping/enumeration attempts even from an authorized user's
    own account.
    """

    scope = "events_list"
