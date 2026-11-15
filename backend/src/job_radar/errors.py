"""Exceptions shared across layers."""


class BoardFetchError(Exception):
    """A board could not be fetched or parsed. The scraper reports it as a
    failure for that board and never caches it."""
