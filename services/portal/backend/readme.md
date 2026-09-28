# FastApi backend

### Dependencies
- pip install "fastapi[all]"

### Start serve
```bash
uvicorn main:app --reload
# start with uv
uv run fastapi run app/main.py --port 8000 --host 0.0.0.0 
```

### Docker

- build
```bash
docker-compose up
```
- uninstall
```bash
docker-compose down
```
- paste your original dicom cases into ~/primary.
- update your manifest.xlsx file.