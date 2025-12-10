# fix problems introduced by a bug in line 90 of 
#    services/portal/DigitalTWINS-Portal/backend/app/main.py
# (change get to post)

cd ~/digitaltwins-platform && \
git submodule update --init --recursive && \
cd services/portal/DigitalTWINS-Portal && git pull origin main && cd ../../.. && \
cd services/api/digitaltwins-api && git pull origin main && cd ../../.. && \
docker compose down

# Fix line 90 of services/portal/DigitalTWINS-Portal/backend/app/main.py

docker compose build portal-backend && \
docker compose down && \
docker compose up -d
