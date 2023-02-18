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
import whisper
from flask import Flask
import threading
from time import sleep
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Use a service account.
cred = credentials.Certificate(r'./whispertranscribe-firebase-adminsdk-ae5w6-6383202849.json')
app = firebase_admin.initialize_app(cred)
db = firestore.client()


# Create an Event for notifying main thread.
callback_done = threading.Event()

def on_snapshot(col_snapshot, changes, read_time):
    print(u'Callback received query snapshot.')
    print(u'Current values: ')
    for change in changes:
        if change.type.name == 'ADDED':
            print('A')
            query = db.collection(u'user_audio').where(u'document_id', u'==', change.document.id)
            docs = query.stream()
            for doc in docs:

                #try catch/error status
                try:
                    #extract values and transcribe
                    print(u'New ADDED entry detected: {}'.format(change.document.id))
                    print(doc.to_dict())
                    mod = db.collection(u'user_audio').document(change.document.id)
                    mod.update({u'status': "PROCESSING"})

                    start_time = time.time()
                    model = whisper.load_model("base.en")
                    print("Starting to process video.\n")
                    #result = model.transcribe(doc.to_dict()['path'])
                    result = {'text':'poopoo'}
                    print("Processing complete.")
                    print("\nCompleted in ---%s seconds" % (time.time() - start_time))
                    transcript = result['text'] #os.environ.get("NAME", "World")
                    print(transcript)
                    mod.update({u'transcript': transcript})

                    #TO-DO: multithreading and deleting file

                    print('**************great success*********')

                    mod.update({u'status': "COMPLETE\n\n"})
                except Exception as e:
                    mod.update({u'status': "ERROR"})
                    print(e)
                    print("Critical error. Processing impossible.\n\n")
        
        elif change.type.name == 'MODIFIED':
            print('B')
            query = db.collection(u'user_audio').where(u'status', u'==', u'UPLOADED')
            docs = query.stream()
            for doc in docs:

                #try catch/error status
                try:
                    #extract values and transcribe
                    print(u'New entry/UPLOADED detected: {}'.format(change.document.id))
                    print(doc.to_dict())
                    mod = db.collection(u'user_audio').document(change.document.id)
                    mod.update({u'status': "PROCESSING"})

                    start_time = time.time()
                    model = whisper.load_model("base.en")
                    print("Starting to process video.\n")
                    #result = model.transcribe(doc.to_dict()['path'])
                    result = {'text':'poopoo'}
                    print("Processing complete.")
                    print("\nCompleted in ---%s seconds" % (time.time() - start_time))
                    transcript = result['text'] #os.environ.get("NAME", "World")
                    print(transcript)
                    mod.update({u'transcript': transcript})

                    #TO-DO: multithreading and deleting file

                    print('**************great success*********')

                    mod.update({u'status': "COMPLETE\n\n"})
                except Exception as e:
                    mod.update({u'status': "ERROR"})
                    print(e)
                    print("Critical error. Processing impossible.\n\n")

    callback_done.set()
        # Removed other cases

# db = quickstart_new_instance()

col_query = db.collection(u'user_audio')

# Watch the collection query
query_watch = col_query.on_snapshot(on_snapshot)

app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", 
port=int(os.environ.get("PORT", 8080)))