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
        transcript_status = notebookData['transcript_status'];
    except Exception as e:
        print(f"Transcript Status not found on document {document.id}. Skipping.")
        return
    if(transcript_status != 'QUEUED'):
        print(f"Transcript Status not QUEUED on document {document.id}. Skipping.")
        return

    print(f'Starting transcription on : {document.id}.')
    try:
        #extract values and transcribe
        mod = document._reference
        start_time = Timestamp()
        start_time.GetCurrentTime()
        mod.update({u'status': "PROCESSING", "transcript_processing_started_at": start_time.ToDatetime()})

        audio_url = notebookData['audio_url']
        if(audio_url == None):
            raise Exception("Audio URL not found")
        print(f"Starting to process video. {audio_url} \n")
        result = model.transcribe(notebookData['audio_url'])
        print("Processing complete.")

        end_time = Timestamp()
        end_time.GetCurrentTime()
        print("\nCompleted in ---%s seconds" % (end_time.ToSeconds() - start_time.ToSeconds()))
        transcript = result['text'] #os.environ.get("NAME", "World")
        # Print first 100 characters of transcript with ... appended
        print(transcript[:100] + "...\n")
        mod.update({u'transcript': transcript, 'transcript_processing_completed_at': end_time.ToDatetime(), 'transcript_status': 'COMPLETE'})
        print(f"Transcription complete on Document: {document.id}\n")

    except Exception as e:
        print(f"Processing Error on Document: {document.id}:")
        print(e);
        print("\n\n")

        try:
            mod.update({'transcript_status': 'ERROR', 'transcription_error': e.args})
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