from rest_framework.throttling import UserRateThrottle


class ImportRateThrottle(UserRateThrottle):
    scope = 'import'
    rate = '5/hour'
