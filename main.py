#!/usr/bin/env python
#
# Copyright 2008 Ryan Raaum
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from sites2seq import sites2seq

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')

def _404error(handler):
    """Standard 404 actions for any RequestHandler."""
    handler.error(404)
    template_values = { 'url': handler.request.url }
    path = os.path.join(TEMPLATES, '404.html')
    handler.response.out.write(template.render(path, template_values))

class MainHandler(webapp.RequestHandler):
    def get(self):
        template_values = {}
        path = os.path.join(TEMPLATES, 'index.html')
        self.response.out.write(template.render(path, template_values))
    
class Sites2SeqHandler(webapp.RequestHandler):
    def get(self, action):
        if action == "" or action == "main":
            template_values = {}
            path = os.path.join(TEMPLATES, 'sites2seq_main.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)
            
    def post(self, action):
        self.response.out.write(action)

class NoSuchURLHandler(webapp.RequestHandler):
    def get(self):
        _404error(self)
    
    def post(self):
        _404error(self)

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/sites2seq/(.*)', Sites2SeqHandler),
        ('/.*', NoSuchURLHandler),
        ],debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()
