pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(false)
    }

    environment {
        ENABLE_LIVE_AGENTS = 'false'
        DOCKER_BUILDKIT = '1'
        COMPOSE_DOCKER_CLI_BUILD = '1'
        BACKEND_IMAGE = "ola-ai-data-agent-backend:${env.BUILD_NUMBER}"
        FRONTEND_IMAGE = "ola-ai-data-agent-frontend:${env.BUILD_NUMBER}"
        ECR_REGISTRY = '271825826985.dkr.ecr.ap-south-1.amazonaws.com'
        AWS_REGION = 'ap-south-1'
        BACKEND_ECR_IMAGE = "271825826985.dkr.ecr.ap-south-1.amazonaws.com/ola-ai-data-agent-backend:${env.BUILD_NUMBER}"
        FRONTEND_ECR_IMAGE = "271825826985.dkr.ecr.ap-south-1.amazonaws.com/ola-ai-data-agent-frontend:${env.BUILD_NUMBER}"
    }

    stages {
        stage('Backend tests') {
            steps {
                sh '''
                    docker run --rm \
                        --user "$(id -u):$(id -g)" \
                        --env HOME=/tmp \
                        --mount type=bind,source="$WORKSPACE",target=/workspace \
                        --workdir /workspace \
                        python:3.13-slim \
                        sh -eu -c '
                            python -m venv /tmp/venv
                            /tmp/venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check . pytest httpx
                            /tmp/venv/bin/python -m pytest -q
                        '
                '''
            }
        }

        stage('Frontend tests and build') {
            steps {
                sh '''
                    docker run --rm \
                        --user "$(id -u):$(id -g)" \
                        --env HOME=/tmp \
                        --env npm_config_cache=/tmp/npm-cache \
                        --mount type=bind,source="$WORKSPACE",target=/workspace \
                        --workdir /workspace/frontend \
                        node:24-bookworm-slim \
                        sh -eu -c '
                            npm ci
                            npm test -- --run
                            npm run build
                        '
                '''
            }
        }

        stage('SonarQube analysis') {
            steps {
                script {
                    if (!env.SONAR_HOST_URL?.trim()) {
                        echo 'SonarQube analysis skipped: SONAR_HOST_URL is not configured.'
                    } else {
                        withSonarQubeEnv('sonarqube') {
                            sh '''
                                if command -v sonar-scanner >/dev/null 2>&1; then
                                    sonar-scanner
                                else
                                    echo 'SonarQube analysis skipped: sonar-scanner is unavailable on the Jenkins agent.'
                                fi
                            '''
                        }
                    }
                }
            }
        }

        stage('Build Docker images') {
            steps {
                sh 'docker build --pull --no-cache --build-arg DEPENDENCY_INSTALL_REVISION="$BUILD_NUMBER" --file Dockerfile --tag "$BACKEND_IMAGE" .'
                sh 'docker build --file frontend/Dockerfile --tag "$FRONTEND_IMAGE" frontend'
                sh '''
                    docker run --rm --entrypoint python "$BACKEND_IMAGE" -c 'import importlib.metadata as m; from packaging.version import Version; r={"msgpack":"1.2.1","setuptools":"78.1.1","urllib3":"2.8.0"}; [(print(f"{p} {v}") or (_ for _ in ()).throw(SystemExit(f"{p} {v} is below required {n}"))) if Version((v:=m.version(p))) < Version(n) else print(f"{p} {v}") for p,n in r.items()]'
                    docker run --rm --entrypoint sh "$BACKEND_IMAGE" -eu -c '
                        check_absent() {
                            for path in "$@"; do
                                if [ -e "$path" ]; then
                                    echo "Unexpected runtime package path: $path" >&2
                                    exit 1
                                fi
                            done
                        }

                        check_present() {
                            for path in "$@"; do
                                if [ ! -e "$path" ]; then
                                    echo "Missing patched runtime package path: $path" >&2
                                    exit 1
                                fi
                            done
                        }

                        check_absent \
                            /opt/venv/bin/pip \
                            /opt/venv/bin/pip3 \
                            /opt/venv/bin/pip3.13 \
                            /opt/venv/lib/python3.13/site-packages/pip \
                            /opt/venv/lib/python3.13/site-packages/pip-*.dist-info \
                            /usr/local/bin/pip \
                            /usr/local/bin/pip3 \
                            /usr/local/bin/pip3.13 \
                            /usr/local/lib/python3.13/site-packages/pip \
                            /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
                            /usr/local/lib/python3.13/site-packages/setuptools \
                            /usr/local/lib/python3.13/site-packages/setuptools-*.dist-info

                        check_present \
                            /opt/venv/lib/python3.13/site-packages/setuptools \
                            /opt/venv/lib/python3.13/site-packages/setuptools-*.dist-info

                        echo "Runtime package cleanup validation passed."
                    '
                '''
            }
        }

        stage('Trivy security scan') {
            steps {
                sh '''
                    if command -v trivy >/dev/null 2>&1; then
                        trivy image --config="" --ignorefile="" --secret-config="" --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$BACKEND_IMAGE"
                        trivy image --config="" --ignorefile="" --secret-config="" --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$FRONTEND_IMAGE"
                    else
                        echo 'ERROR: Trivy is unavailable on the Jenkins agent; refusing to continue.' >&2
                        exit 1
                    fi
                '''
            }
        }

        stage('Push images to ECR') {
            steps {
                sh '''
                    set -eu
                    docker_config=$(mktemp -d)
                    trap 'rm -rf "$docker_config"' EXIT
                    export DOCKER_CONFIG="$docker_config"

                    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
                    docker tag "$BACKEND_IMAGE" "$BACKEND_ECR_IMAGE"
                    docker tag "$FRONTEND_IMAGE" "$FRONTEND_ECR_IMAGE"
                    docker push "$BACKEND_ECR_IMAGE"
                    docker push "$FRONTEND_ECR_IMAGE"
                '''
            }
        }

        stage('Deploy to EC2') {
            steps {
                sh '''
                    set -eu
                    if ss -ltnH '( sport = :80 )' | grep -q .; then
                        echo 'Deployment aborted: host port 80 is already occupied.' >&2
                        ss -ltnp '( sport = :80 )' || true
                        exit 1
                    fi

                    docker_config=$(mktemp -d)
                    trap 'rm -rf "$docker_config"' EXIT
                    export DOCKER_CONFIG="$docker_config"

                    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
                    export IMAGE_TAG="$BUILD_NUMBER"
                    docker compose -f docker-compose.deploy.yml pull backend frontend
                    docker compose -f docker-compose.deploy.yml up -d --remove-orphans --wait --wait-timeout 120
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image rm "$BACKEND_IMAGE" "$FRONTEND_IMAGE" "$BACKEND_ECR_IMAGE" "$FRONTEND_ECR_IMAGE" 2>/dev/null || true'
            cleanWs()
        }
    }
}
