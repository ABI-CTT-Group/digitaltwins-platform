# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update


VERSION_STRING='5:27.3.1-1~ubuntu.24.04~noble'

sudo apt-get install \
  docker-ce=$VERSION_STRING \
  docker-ce-cli=$VERSION_STRING \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo apt-mark hold docker-ce docker-ce-cli

sudo usermod -aG docker $USER
# Log out and log back in for this to take effect
