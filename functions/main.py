import os
from imageio.v2 import imread, imwrite
import json
import base64
import random
from google.cloud import storage
import functions_framework
import imgaug.augmenters as iaa
from concurrent import futures
from google.cloud import pubsub_v1
import urllib.request

topics = {
    'grayscale': 'grayscale-iaaas-8',
    'gaussian-blur': 'gaussian-blur-iaaas-8',
    'sharpen': 'sharpen-iaaas-8',
    'multiply_brightness': 'multiply-brightness-iaaas-8',
    'change_color_temp': 'change-color-temp-iaaas-8',
    'flip': 'flip-iaaas-8',
}

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

def get_callback(publish_future, data):
    '''
    Checks if publish call succeeds in 60s else returns timed out exception
    Source: https://cloud.google.com/pubsub/docs/publisher#python
    '''
    def callback(publish_future):
        try:
            # Wait 60 seconds for the publish call to succeed.
            print(publish_future.result(timeout=60))
        except futures.TimeoutError:
            print(f"Publishing {data} timed out.")

    return callback

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
        upload_blob('iaaas-8-input', f'/tmp/{output_imgname}', output_imgname)
        next_op = message['next'].pop()
        ## message = {"image_identifier" : "output_imgname", "next": message['next'], "output_folder": message["output_folder"]}
        publisher = pubsub_v1.PublisherClient()
        
        # Get path to topic 
        ## Get project id from metadata server
        url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        req = urllib.request.Request(url)
        req.add_header("Metadata-Flavor", "Google")
        project_id = urllib.request.urlopen(req).read().decode()
        topic_id = topics[next_op]
        topic_path = publisher.topic_path(project_id, topic_id)
        
        # The following snippet is from https://cloud.google.com/pubsub/docs/publisher#python
        publish_futures = []
        new_message = {"image_identifier": output_imgname, "next": message['next'], "output_folder": message["output_folder"]}
        data = json.dumps(new_message)
        
        # When you publish a message, the client returns a future.
        publish_future = publisher.publish(topic_path, data.encode("utf-8"))
        
        # Non-blocking. Publish failures are handled in the callback function.
        publish_future.add_done_callback(get_callback(publish_future, data))
        publish_futures.append(publish_future)

        # Wait for all the publish futures to resolve before exiting.
        futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)

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

@functions_framework.cloud_event
def sharpen(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.Sharpen(alpha=1.0)])
    perform_augmentation(message, augmenter, "_sharp")

@functions_framework.cloud_event
def multiply_brightness(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.MultiplyBrightness(1.5)])
    perform_augmentation(message, augmenter, "_bright")

@functions_framework.cloud_event
def change_color_temp(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.ChangeColorTemperature(1100)])
    perform_augmentation(message, augmenter, "_colortemp")

@functions_framework.cloud_event
def flip(cloud_event):
    # Decode message from Pub/Sub
    message = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    message = json.loads(message)
    print('Decoded message')

    # Create augmenter and augment the image
    augmenter = iaa.Sequential([iaa.Fliplr()])
    perform_augmentation(message, augmenter, "_flip")