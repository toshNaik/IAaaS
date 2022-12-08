from flask import Flask, url_for, send_from_directory, request, render_template
import logging, os
#from werkzeug import secure_filename
#from imageio.v2 import imread, imwrite
import json
import jsonpickle
import base64
import random
from google.cloud import storage
from concurrent import futures
from google.cloud import pubsub_v1
import urllib.request
import hashlib
from typing import List

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
project_id='radiant-arcade-369302'

topics = {
    'grayscale': 'grayscale-iaaas-8',
    'gaussian-blur': 'gaussian-blur-iaaas-8',
}

def set_bucket_public_iam(bucket_name):
    """Set a public IAM Policy to bucket"""
    print("Making bucket public")
    members=["allUsers"]
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    policy = bucket.get_iam_policy(requested_policy_version=3)
    policy.bindings.append(
        {"role": "roles/storage.objectViewer", "members": members}
    )

    bucket.set_iam_policy(policy)

    print(f"Bucket {bucket.name} is now publicly readable")


def get_or_create_bucket(bucket_name):
    '''Function to get bucket if it exists else create it and then return bucket'''
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        return client.get_bucket(bucket_name)
    bucket.storage_class = 'STANDARD'
    new_bucket = client.create_bucket(bucket, location="us")
    return new_bucket

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

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    '''
    Uploads [source_file] to [destination_blob] in [bucket_name]
    '''
    bucket = get_or_create_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/', methods = ['POST'])
def api_root():
    if request.method == 'POST' and request.files['file']:
        input_bucket_name='iaaas-8-input123'
        img = request.files['file']
        input_imgname = str(hashlib.sha224(img.filename.encode('utf-8')).hexdigest()) + '.jpeg'
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], input_imgname))
        bucket = get_or_create_bucket(input_bucket_name)
        print('Got input bucket')
        set_bucket_public_iam(input_bucket_name)
        upload_blob(input_bucket_name, f'static/uploads/{input_imgname}', input_imgname)
        output_foldername=input_imgname.split('.')[0]+'_augmented'
        print('Done!')
        os.remove("./static/uploads/"+input_imgname)  
        aug_seq = request.form['aug_seq']  
        #print(aug_seq)    
        operations= request.form.getlist("augmentation")
        #next_op='grayscale'
        url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        req = urllib.request.Request(url)
        req.add_header("Metadata-Flavor", "Google")
        #project_id = urllib.request.urlopen(req).read().decode()
        #to-do: chain augmentation
        if(aug_seq=='single'):
            for next_op in operations:
                topic_id = topics[next_op]
                publisher = pubsub_v1.PublisherClient()
                topic_path = publisher.topic_path(project_id, topic_id)
                publish_futures = []
                new_message = {"image_identifier": str(input_imgname), "next": [], "output_folder": str(output_foldername)}
                data = json.dumps(new_message)
                # When you publish a message, the client returns a future.
                publish_future = publisher.publish(topic_path, data.encode("utf-8"))
                # Non-blocking. Publish failures are handled in the callback function.
                publish_future.add_done_callback(get_callback(publish_future, data))
                publish_futures.append(publish_future)
                # Wait for all the publish futures to resolve before exiting.
                futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)
        elif(aug_seq=='chain'):
            next_op=operations.pop(0)
            print(operations)
            topic_id = topics[next_op]
            publisher = pubsub_v1.PublisherClient()
            topic_path = publisher.topic_path(project_id, topic_id)
            publish_futures = []
            new_message = {"image_identifier": str(input_imgname), "next": operations, "output_folder": str(output_foldername)}
            data = json.dumps(new_message)
            # When you publish a message, the client returns a future.
            publish_future = publisher.publish(topic_path, data.encode("utf-8"))
            # Non-blocking. Publish failures are handled in the callback function.
            publish_future.add_done_callback(get_callback(publish_future, data))
            publish_futures.append(publish_future)
            # Wait for all the publish futures to resolve before exiting.
            futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)
        output_data=augmented(output_foldername)
        return render_template('output_page.html', data=output_data)
    else:
        output_data=["NoData"]
        return render_template('output_page.html', data=output_data)
        
    #response_pickled = jsonpickle.encode(response)

def augmented(output_foldername):
    output_data=[]
    output_bucket='iaaas-8-output123'
    set_bucket_public_iam(output_bucket)
    storage_client = storage.Client()
    for blob in storage_client.list_blobs(output_bucket, prefix=output_foldername):
        output_image=str(blob.name)
        print(output_image)
        link="https://storage.googleapis.com/{0}/{1}".format(output_bucket,output_image)
        output_data.append(link)
    return output_data

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)