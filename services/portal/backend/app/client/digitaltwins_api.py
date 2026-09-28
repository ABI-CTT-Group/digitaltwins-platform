import httpx
from typing import Optional, Dict, Any
import os


class DigitalTWINSAPIClient:
    """
    Digital TWINS API
    Support Basic Auth and Token Auth。
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
    ):
        _url = os.getenv('DIGITALTWINS_API_BASE_URL', "http://localhost").rstrip('/')
        _port = os.getenv('DIGITALTWINS_API_PORT', '8000')
        self.base_url = f"{_url}:{_port}"
        self.username = username
        self.password = password
        self.token = token
        self.client = httpx.AsyncClient()

    def _get_auth_headers(self) -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()

        auth = None
        if self.username and self.password and not self.token:
            auth = (self.username, self.password)

        response = await self.client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=headers,
            auth=auth,
            timeout=15.0,
        )
        response.raise_for_status()
        return response

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None):
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None):
        return await self.request("POST", endpoint, json=json)

    async def close(self):
        await self.client.aclose()
