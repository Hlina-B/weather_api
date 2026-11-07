import requests
import logging

logger = logging.getLogger(__name__)

def http_request(url: str, tout=15, header: dict = None):
    if header is None:
        header = {"Accept": "application/json"}
    response = requests.get(url, headers=header, timeout=tout)
    response.raise_for_status()

    return response.json()
