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
                sh 'python3.13 -m pytest -q'
            }
        }

        stage('Frontend tests and build') {
            steps {
                dir('frontend') {
                    sh 'npm ci'
                    sh 'npm test -- --run'
                    sh 'npm run build'
                }
            }
        }

        stage('SonarQube analysis') {
            when {
                expression { return env.SONAR_HOST_URL?.trim() }
            }
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        if command -v sonar-scanner >/dev/null 2>&1; then
                            sonar-scanner
                        else
                            echo "sonar-scanner is unavailable; skipping analysis"
                        fi
                    '''
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
                        trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$BACKEND_IMAGE"
                        trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$FRONTEND_IMAGE"
                    else
                        echo "trivy is unavailable; skipping image scan"
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
