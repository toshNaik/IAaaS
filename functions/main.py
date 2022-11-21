import os
from imageio.v2 import imread, imwrite
import json
import base64
import random
from google.cloud import storage
import functions_framework
import imgaug.augmenters as iaa

def get_or_create_bucket(bucket_name):
    '''Function to get bucket if it exists else create it and then return bucket'''
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        return client.get_bucket(bucket_name)
    bucket.storage_class = 'STANDARD'
    new_bucket = client.create_bucket(bucket, location="us")
    return new_bucket

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    '''
    Uploads [source_file] to [destination_blob] in [bucket_name]
    '''
    bucket = get_or_create_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

def perform_augmentation(message, augmenter, name_stub):
    '''
    Gets image from input bucket, performs augmentation and stores the result image in the output bucket
    with name_stub and random integer appended to image_identifier name.
    '''
    # Obtain input bucket
    bucket = get_or_create_bucket('iaaas-8-input')
    print('Got input bucket')

    # Get image from bucket and download to tmp folder
    blob = bucket.get_blob(message['image_identifier'])
    image_name = message['image_identifier']
    blob.download_to_filename(f'/tmp/{message["image_identifier"]}')
    print('Downloaded image from input bucket')

    # Perform augmentation on the image
    img = imread(f'/tmp/{message["image_identifier"]}')
    aug = augmenter(image=img)
    imgname, ext = os.path.splitext(message["image_identifier"])
    output_imgname = imgname + name_stub + str(random.randint(100,999)) + ext
    imwrite(f'/tmp/{output_imgname}', aug)
    print('Performed augmentation')
    
    # Perform next operation
    ## No next operation, then upload to output bucket
    if len(message['next']) == 0:
        output_folder = message['output_folder']
        destination = os.path.join(output_folder, output_imgname)
        upload_blob('iaaas-8-output', f'/tmp/{output_imgname}', destination)
        print('Done!')
    ## If there is following operation then put result back in to input bucket
    ## and publish to topic of that operation
    else:
        next_op = message['next'].pop()
        upload_blob('iaaas-8-input', f'/tmp/{output_imgname}', output_imgname)
        # TODO: Publish message to next operation topic
        ## message = {"image_identifier" : "output_imgname", "next": message['next'], "output_folder": message["output_folder"]}

@functions_framework.cloud_event
def gaussian_blur(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.GaussianBlur(sigma=3.0)])
    perform_augmentation(message, augmenter, "_gb")

@functions_framework.cloud_event
def grayscale(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.Grayscale(alpha=1.0)])
    perform_augmentation(message, augmenter, "_gray")
