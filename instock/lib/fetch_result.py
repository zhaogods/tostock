#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class FetchStatus:
    SUCCESS = 'success'
    EMPTY = 'empty'
    API_ERROR = 'api_error'
    RATE_LIMIT = 'rate_limit'
    NETWORK_ERROR = 'network_error'
    PARTIAL = 'partial'


class FetchResult:
    def __init__(self, status, data=None, message=''):
        self.status = status
        self.data = data
        self.message = message

    @property
    def is_success(self):
        return self.status == FetchStatus.SUCCESS

    @property
    def should_retry(self):
        return self.status in (FetchStatus.NETWORK_ERROR, FetchStatus.RATE_LIMIT)
