# FastApi backend

### Dependencies
- pip install "fastapi[all]"

### Start serve
```bash
uvicorn main:app --reload
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