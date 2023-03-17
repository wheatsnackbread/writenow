# Copyright 2017 Google, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,firebase-admin
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import time
from typing import Optional
import whisper
from flask import Flask
import threading
from time import sleep
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import google.cloud.firestore_admin_v1.types.firestore_admin
from enum import Enum
from google.protobuf.timestamp_pb2 import Timestamp
from urllib.parse import quote 
from requests import get
# class syntax

class AudioProcessingStatus(Enum):
    IDLE = 'IDLE'
    QUEUED = 'QUEUED'
    ERROR = 'ERROR'
    PROCESSING = 'PROCESSING'
    COMPLETE = 'COMPLETE'


# Use a service account.
cred = credentials.Certificate(r'./whispertranscribe-admin.key.json')
app = firebase_admin.initialize_app(cred)
db : firestore._FirestoreClient = firestore.client()
# Create an Event for notifying main thread.
callback_done = threading.Event()

class Notebook:
    id: str
    title: str
    audio_path: str
    audio_url: Optional[str]
    user_id: str

    transcript_status: AudioProcessingStatus
    summary_status: AudioProcessingStatus

    transcript: Optional[str];
    notebook_users: list[str];

    created_at: Timestamp;
    transcript_processing_started_at: Optional[Timestamp];
    transcript_processing_completed_at: Optional[Timestamp];
    summary_processing_started_at: Optional[Timestamp];
    summary_processing_completed_at: Optional[Timestamp];


model = whisper.load_model("base.en")

def triggerTranscribe(document: firestore.firestore.DocumentSnapshot):
    notebookData : Notebook = document.__dict__['_data'];
    transcript_status = None
    try:
        transcript_status = notebookData['transcript_response']['status']
        print(transcript_status)
    except Exception as e:
        print(f"Transcript Status not found on document {document.id}. Skipping.")
        return
    if(transcript_status != 'IDLE'):
        print(f"Transcript Status not IDLE on document {document.id}. Skipping.")
        return

    print(f'Starting transcription on : {document.id}.')
    try:
        #extract values and transcribe
        mod = document._reference
        start_time = Timestamp()
        start_time.GetCurrentTime()
        mod.update({u'transcript_response.status': "PROCESSING", "transcript_response.timestamp.started_at": start_time.ToDatetime()})

        print("A")

        #audio_url = urllib.quote(r'https://firebasestorage.googleapis.com/v0/b/whispertranscribe.appspot.com/o/' + notebookData['audio_path'])
        # WRONG !

        audio_url = r'https://firebasestorage.googleapis.com/v0/b/whispertranscribe.appspot.com/o/' + quote(str(notebookData['audio_path']).encode('utf8'), safe=r'\':()') + '?alt=media'

        print('AUDIO_URL:    ' + audio_url)

        print("B")

        #audio_url = r'https://firebasestorage.googleapis.com/v0/b/whispertranscribe.appspot.com/o/' + quote((r"notebook_audio/4W4qs99_SpAqMEU086xp4/onlymp3.to - The NY Subway's Weirdly Successful Lost and Found System-dwAxPVlKwoQ-256k-1654739305338 (1).mp3").encode('utf8'),  safe=r'\':()') + '?alt=media'


        if(audio_url == None):
            print("Audio URL not found")
            raise Exception("Audio URL not found")
        
        print("C")
            
        print(f"Starting to process video. {audio_url} \n")

        time.sleep(5) #gotta wait or it tries to process before it is fully uploaded, or else u get a stinky 404

        upload_status = 0

        # lowkey stupid code but you gotta do what you gotta do when the Python SDK doesn't support on upload completion triggers
        for i in range(6):
            upload_status = get(audio_url).status_code
            if upload_status == 200:
                print("File successfully detected in Firestore.")
                break
            else:
                print("File not completed uploaded or errored. Trying again in 20 seconds.")
                time.sleep(20)

        if upload_status != 200:
            raise Exception("Audio file did not upload at all or took too long and timed out.")

    
        result = model.transcribe(audio_url)
        print("Processing complete.")

        print("D")

        end_time = Timestamp()
        end_time.GetCurrentTime()
        print("\nCompleted in ---%s seconds" % (end_time.ToSeconds() - start_time.ToSeconds()))
        transcript = result['text'] #os.environ.get("NAME", "World")
        # Print first 100 characters of transcript with ... appended
        print(transcript[:100] + "...\n")

        print("E")

        mod.update({u'transcript_response.result.val.transcript': transcript,  'transcript_response.timestamp.completed_at': end_time.ToDatetime(), 'transcript_response.status': 'SUCCESS', 'transcript_response.result.status': 'SUCCESS'})
                   
        time.sleep(2)

        mod.update({'summary_response.status': 'QUEUED'}) #QUEUED after a couple seconds to begin the summarization process
        print(f"Transcription complete on Document: {document.id}\n")

    except Exception as e:
        print(f"Processing Error on Document: {document.id}:")
        print(e);
        print("\n\n")

        try:
            mod.update({'transcript_response.status': 'ERROR', 'transcription_error': e.args})
            print(f"Document Updated with Error: {document.id}\n")
        except Exception as e2:
            print(f"CRITICAL ERROR: Updating Document Failed. {document.id}")
            print(e2)
            print("\n\n")
    finally:
        print(f"Transcription Finished on Document: {document.id}\n")





def on_snapshot(col_snapshot, changes, read_time):
    # print(u'Callback received query snapshot.')
    # print(u'Current values: ')

    for change in changes:
        if(change.type.name == 'ADDED' or change.type.name == 'MODIFIED'):
            triggerTranscribe(change.document)
    callback_done.set()
        # Removed other cases

# db = quickstart_new_instance()

col_query = db.collection(u'notebooks')

# Watch the collection query
query_watch = col_query.on_snapshot(on_snapshot)

app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", 
port=int(os.environ.get("PORT", 8080)))
