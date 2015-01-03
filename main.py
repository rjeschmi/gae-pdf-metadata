#!/usr/bin/python
#
# Copyright (C) 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'rjeschmi@gmail.com (Robert Schmidt)'

import os
import sys

sys.path.insert(0, 'google-api-python-client-gae-1.2.zip')
sys.path.insert(1, 'PyPDF2.zip')

import httplib2
import urllib
from apiclient import discovery
from oauth2client import appengine
from oauth2client import client
from oauth2client.appengine import OAuth2DecoratorFromClientSecrets
from google.appengine.api import memcache
from google.appengine.api import app_identity

import cloudstorage as gcs

from oauth2client.appengine import simplejson as json

import webapp2
import jinja2

import StringIO
from PyPDF2 import PdfFileReader

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])

DEFAULT_GCS_BUCKET = app_identity.get_default_gcs_bucket_name()

# Helpful message to display in the browser if the CLIENT_SECRETS file
# is missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
<h1>Warning: Please configure OAuth 2.0</h1>
<p>
To make this sample run you will need to populate the client_secrets.json file
found at:
</p>
<p>
<code>%s</code>.
</p>
<p>with information found on the <a
href="https://code.google.com/apis/console">APIs Console</a>.
</p>
""" % CLIENT_SECRETS


decorator = OAuth2DecoratorFromClientSecrets(
    CLIENT_SECRETS,
    scope='https://www.googleapis.com/auth/drive',
    message=MISSING_CLIENT_SECRETS_MESSAGE)

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

class MainHandler(webapp2.RequestHandler):
    @decorator.oauth_aware
    def get(self):
        variables = {
            'url': decorator.authorize_url(),
            'has_credentials': decorator.has_credentials()
            }
        template = JINJA_ENVIRONMENT.get_template('grant.html')
        self.response.write(template.render(variables))


class PDFHandler(webapp2.RequestHandler):
    @decorator.oauth_required
    def __init__(self):
        self._http=decorator.http()
        self._drive_service = discovery.build ('drive', 'v2', http=self._http)
        self._pdf_helper = PDFHelper(self._drive_service)

    def get(self, doc_id):
        file = self._pdf_helper.pdf_metadata(doc_id)
        self.response.headers['Content-Type'] = 'text/html'
        self.response.write(json.dumps(file))

class PDFHelper():
    def __init__(self, service):
        self._drive_service = service

    def pdf_metadata(self,doc_id):
        file = self._drive_service.files().get(fileId=doc_id).execute()
        downloadUrl = file.get('downloadUrl')
        if downloadUrl :
            pdf_content = StringIO.StringIO()
            resp, content = self._drive_service._http.request(downloadUrl)
            pdf_content.write(content)
            pdf = PdfFileReader(pdf_content)
            file['page_nums']=pdf.getNumPages()
        return file

        

class FolderHandler(webapp2.RequestHandler):
    @decorator.oauth_required

    def get(self, folder_name):
        self._http=decorator.http()
        self._drive_service = discovery.build('drive','v2',http=self._http)
        q = "title = '%s'" % (folder_name)
        folder = self._drive_service.files().list(q=q).execute()
        folder_id = folder['items'][0]['id']
        children = self._find_children(folder_id)
        self.response.headers['Content-Type'] = 'application/json'
        pdf = PDFHelper(self._drive_service)
        #children = self._drive_service.children().list(folderId=folder_id).execute()
        #self.response.write(json.dumps(children))
        pdfs = []
        for child in children:
            pdf_out = pdf.pdf_metadata(doc_id=child['id']) 
            pdfs.append(pdf_out)
        self.response.write(json.dumps(pdfs))

    def _find_children(self, folder_id):
        children = self._drive_service.children().list(folderId=folder_id).execute()
        pdfs = []
        for child in children.get('items', []):
            file = self._drive_service.files().get(fileId=child['id']).execute()
            if file['mimeType'] == FOLDER_MIME_TYPE:
                pdfs = pdfs + self._find_children(child['id'])
            else:
                pdfs.append(file)

        return pdfs


app = webapp2.WSGIApplication(
    [
     ('/', MainHandler),
     (r'/pdf/count/(.+)', PDFHandler),
     (r'/folder/count/(.+)', FolderHandler),
     (decorator.callback_path, decorator.callback_handler()),
    ],
    debug=True) 
