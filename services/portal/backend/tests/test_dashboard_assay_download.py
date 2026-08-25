import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.router.dashboard import get_client

client = TestClient(app)

def test_assay_download():
    mock_digitaltwins_client = AsyncMock()
    
    mock_response = AsyncMock()
    mock_response.headers = {"Content-Disposition": 'attachment; filename="assay_38_results.zip"'}
    
    async def mock_aiter_bytes():
        yield b"mock zip data part 1"
        yield b"mock zip data part 2"
        
    mock_response.aiter_bytes = mock_aiter_bytes
    mock_digitaltwins_client.get_stream.return_value = mock_response

    # override dependency
    app.dependency_overrides[get_client] = lambda: mock_digitaltwins_client

    # Call endpoint directly, we don't need auth since get_client is overridden
    # Wait, get_client depends on get_token which might throw 401. Let's see if overriding get_client is enough.
    # Yes, overriding get_client overrides the entire branch.
    # But wait, dashboard router has prefix "/api/dashboard"
    response = client.get("/api/dashboard/assay-download?seek_id=38")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == 'attachment; filename="assay_38_results.zip"'
    assert response.content == b"mock zip data part 1mock zip data part 2"
    
    mock_digitaltwins_client.get_stream.assert_called_once_with("/assays/38/workspace/dataset/download")
    
    # clean up
    app.dependency_overrides.pop(get_client, None)
