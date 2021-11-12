# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#!/bin/bash

# NOTE: If this error occurs during the container image creation section check your limits.
# ERROR: unexpected status code <URL> 429 Too Many Requests - Server message: toomanyrequests: You have reached your pull rate limit.

# Variables
AWS_ACCOUNT_ID=$1
AWS_REGION=$2
VERSION=1.0.0

# List of images to be pushed 
images=("controlplane/upgrade" "controlplane/status" "dataplane/daemonset" "dataplane/nodegroup" "dataplane/status")

for app in ${images[*]}; do
    echo $app

    check_repo=$(aws ecr describe-repositories --region $AWS_REGION --query repositories[*].repositoryName | grep $app)
    if [ -z "$check_repo" ]
    then
      echo "Creating ECR repository $app."
      # Create ECR Repository in the target account for pushing the image.
      aws ecr create-repository \
      --repository-name $app \
      --image-scanning-configuration scanOnPush=true \
      --region $AWS_REGION
    else
      echo "ECR repository $app already exists."
    fi

    echo "Build container image $app."

    # Build and push image to account
    docker rmi $app -f;
    docker build -t $app images/$app/.;
    docker tag $app:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$app:${VERSION};
    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$app:${VERSION};
done