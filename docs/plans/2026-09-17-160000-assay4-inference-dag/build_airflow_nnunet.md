# Building Airflow with nnUNet

To run inference tasks (like `workflow_39`), the Airflow image must be built with the `nnunet_venv` included. This virtual environment contains PyTorch, nnUNetv2, and custom ABI repositories.

Because it pulls from private GitHub repositories, you must provide a GitHub Personal Access Token (PAT) during the build.

## 1. Set up your GitHub Token

Create a `.secrets` directory in your home folder and save your GitHub token (with `repo` read access) into a file named `github_token`.

```bash
mkdir -p ~/.secrets
echo "ghp_your_token_here" > ~/.secrets/github_token
chmod 600 ~/.secrets/github_token
```

## 2. Build the Image

Run the following command from the root of the `digitaltwins-platform` repository. It securely passes your token as an environment variable which Docker Compose will use as a build secret.

```bash
GITHUB_TOKEN=$(cat ~/.secrets/github_token) DOCKER_BUILDKIT=1 docker compose build \
  --build-arg INSTALL_NNUNET=true
```

## 3. Restart Airflow

After the build completes, recreate the Airflow containers to use the newly built image:

```bash
docker compose up -d
```
