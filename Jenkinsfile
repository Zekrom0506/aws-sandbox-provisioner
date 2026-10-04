pipeline {
    agent any

    triggers {
        // Fired by the GitHub webhook on every push.
        githubPush()
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        TF_IN_AUTOMATION   = 'true'
        AWS_DEFAULT_REGION = 'ap-south-1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Unit tests (pytest)') {
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p reports
                    pytest --junitxml=reports/pytest.xml
                '''
            }
            post {
                always {
                    junit 'reports/pytest.xml'
                }
            }
        }

        stage('Terraform plan') {
            steps {
                withCredentials([
                    [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-sandbox-provisioner'],
                    string(credentialsId: 'slack-signing-secret', variable: 'TF_VAR_slack_signing_secret'),
                    string(credentialsId: 'slack-bot-token', variable: 'TF_VAR_slack_bot_token'),
                    file(credentialsId: 'sandbox-provisioner-backend', variable: 'BACKEND_CONFIG'),
                    file(credentialsId: 'sandbox-provisioner-tfvars', variable: 'TFVARS_FILE')
                ]) {
                    dir('terraform') {
                        sh '''
                            terraform init -input=false -reconfigure -backend-config="$BACKEND_CONFIG"
                            terraform plan -input=false -var-file="$TFVARS_FILE" -out=tfplan
                            terraform show -no-color tfplan > tfplan.txt
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'terraform/tfplan.txt', allowEmptyArchive: true
        }
        failure {
            echo 'Build failed. Check the pytest report and the terraform output above.'
        }
    }
}
