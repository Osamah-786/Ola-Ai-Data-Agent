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
                sh 'docker build --file Dockerfile --tag "$BACKEND_IMAGE" .'
                sh 'docker build --file frontend/Dockerfile --tag "$FRONTEND_IMAGE" frontend'
            }
        }

        stage('Trivy security scan') {
            steps {
                sh '''
                    if command -v trivy >/dev/null 2>&1; then
                        trivy image --config="" --ignorefile="" --secret-config="" --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$BACKEND_IMAGE"
                        trivy image --config="" --ignorefile="" --secret-config="" --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$FRONTEND_IMAGE"
                    else
                        echo 'Trivy image scanning skipped: trivy is unavailable on the Jenkins agent.'
                    fi
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image rm "$BACKEND_IMAGE" "$FRONTEND_IMAGE" 2>/dev/null || true'
            cleanWs()
        }
    }
}
