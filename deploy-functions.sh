#!/bin/bash

entrypoints=(grayscale gaussian_blur sharpen multiply_brightness change_color_temp flip)
functions=(grayscale-iaaas-8 gaussian-blur-iaaas-8 sharpen-iaaas-8 multiply-brightness-iaaas-8 change-color-temp-iaaas-8 flip-iaaas-8)
len=${#functions[@]}

for ((idx=0; idx<$len; idx++))
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