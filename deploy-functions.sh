#!/bin/bash
entrypoints=(grayscale gaussian_blur)
functions=(grayscale-iaaas-8 gaussian-blur-iaaas-8)

for idx in 0 1
do
    ENTRYPOINT=${entrypoints[idx]}
    FUNCTION=${functions[idx]}
    
    gcloud pubsub topics create $FUNCTION

    gcloud functions deploy $FUNCTION --gen2 \
            --region us-central1 \
            --source functions \
            --entry-point $ENTRYPOINT \
            --trigger-topic $FUNCTION \
            --memory 512MB \
            --runtime python39
done