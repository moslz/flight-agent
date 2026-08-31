import secrets

from flask import request

_store = {}

def create_link(url: str, post_data: str) -> str:
    link_id = secrets.token_urlsafe(8)
    _store[link_id] = {"url": url, "post_data": post_data}
    return f"{request.host_url.rstrip('/')}/book/{link_id}"


def get_redirect(link_id: str):
    """Returns {'url', 'post_data'} for a stored link, or None if unknown."""
    return _store.get(link_id)