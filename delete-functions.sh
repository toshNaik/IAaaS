#!/bin/bash

for FUNCTION in gaussian-blur-iaaas-8 grayscale-iaaas-8 sharpen-iaaas-8 multiply-brightness-iaaas-8 change-color-temp-iaaas-8 flip-iaaas-8
do
    gcloud functions delete $FUNCTION --gen2 --region us-central1 --quiet
    gcloud pubsub topics delete $FUNCTION
done