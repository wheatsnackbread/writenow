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
cred = credentials.Certificate(r'./whispertranscribe-nuxt.key.json')
app = firebase_admin.initialize_app(cred)
db : firestore._FirestoreClient = firestore.client()
# Create an Event for notifying main thread.
callback_done = threading.Event()

class Notebook:
    id: str
    title: str
    audio_path: str
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


def triggerTranscribe(document: firestore.firestore.DocumentSnapshot):
    print(document.__dict__)
    notebookData : Notebook = document.__dict__['_data'];
    print(notebookData)
    try:
        #extract values and transcribe
        print(u'New ADDED entry detected: {}'.format(document.id))
        mod = document._reference
        mod.update({u'status': "PROCESSING"})

        start_time = time.time()
        model = whisper.load_model("base.en")
        print("Starting to process video.\n")
        result = model.transcribe(notebookData['audio_path'])
        print("Processing complete.")
        print("\nCompleted in ---%s seconds" % (time.time() - start_time))
        transcript = result['text'] #os.environ.get("NAME", "World")
        print(transcript)
        mod.update({u'transcript': transcript})

        #TO-DO: multithreading and deleting file
        print('**************great success*********')
        mod.update({u'transcript_status': "COMPLETE\n\n"})
    except Exception as e:
        print(f"Processing Error on Document: {document.id}\n")
        try:
            mod.update({'transcript_status': 'ERROR', 'transcription_error': e.args})
        except Exception as e:
            print(f"Critical error. Processing impossible. {document.id} \n\n")





def on_snapshot(col_snapshot, changes, read_time):
    # print(u'Callback received query snapshot.')
    # print(u'Current values: ')

    for change in changes:
        if(change.type.name == 'ADDED' or change.type.name == 'MODIFIED'):
            try:
                if(change.document.get('transcript_status') == 'QUEUED'):
                    triggerTranscribe(change.document)
            except Exception as e:
                print("Transcription Error", e)
                try: 
                    change.document._reference.update({'transcript_status': 'ERROR', 'transcription_error': e.args})
                except Exception as e:
                    print("Fatal Error", e);
                    exit()
            finally: 
                print("Transcription Finished on Document: ", change.document.id)
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