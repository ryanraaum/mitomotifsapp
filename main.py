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
import cgi
import re

import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from mitomotifs import seq2sites
from mitomotifs import sites2str
from fasta import iterate_fasta

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
        # get posted parameters
        format = self.request.get('format')
        output = self.request.get('output')
        content = self.request.get('content')
        # validate submission
        problems = []
        valid = True
        if not format in ['motif_only', 'name_and_motif', 'name_n_and_motif']:
            valid = False
            problems.append('given format not one of the acceptable options.')
        if not output in ['hvr1', 'hvr2', 'hvr1and2', 'hvr1to2', 'coding', 'all']:
            valid = False
            problems.append('given output not one of the acceptable options.')
        content_lines = content.split('\n')
        result_lines = []
        if valid:
            for curr_line in content_lines:
                line = re.sub(r'[,;]', '', curr_line)
                if format == 'motif_only':
                    motifs = line
                elif format == 'name_and_motif':
                    split = line.split(' ', 1)
                    if len(split) == 2:
                        name, motifs = split 
                    else:
                        valid = False
                        problems.append('The entry "%s" does not seem to be correctly formatted' % curr_line)
                else:
                    split = line.split(' ', 2)
                    if len(split) == 3:
                        name, n, motifs = split 
                    else:
                        valid = False
                        problems.append('The entry "%s" does not seem to be correctly formatted' % curr_line)
                try:
                    result_lines.append(sites2seq(motifs.encode('utf8')))
                except MitoMotifError, e:
                    valid = False
                    problems.append(e.message)
            
        if not valid:
            self.response.out.write('<h1>INVALID INPUT</h1>')
            self.response.out.write('%s' % problems)
        self.response.out.write('<p>action: %s</p>' % action)
        self.response.out.write('<p>format: %s</p>' % cgi.escape(self.request.get('format')))
        self.response.out.write('<p>output: %s</p>' % cgi.escape(self.request.get('output')))
        self.response.out.write('<p>content: %s</p>' % cgi.escape(self.request.get('content')))
        for entry in result_lines:
            self.response.out.write('<p>result: %s</p>' % entry)

class Seq2SitesHandler(webapp.RequestHandler):
    def get(self, action):
        if action == "" or action == "main":
            template_values = {}
            path = os.path.join(TEMPLATES, 'seq2sites_main.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)
            
    def post(self, action):

        # get posted parameters
        format = self.request.get('format')
        seq_range = self.request.get('seq_range').encode('utf8')
        content = self.request.get('content')

        # validate submission
        problems = []
        valid = True
        if not format in ['single_seq', 'fasta']:
            valid = False
            problems.append('given format not one of the acceptable options.')
        if not seq_range in ['hvr1', 'hvr2', 'hvr1to2', 'coding', 'all']:
            valid = False
            problems.append('given sequence range not one of the acceptable options.')

        # pull names and sequence out of submitted content
        content = content.encode('utf8')
        names = []
        seqs = []
        if format == 'fasta':
            for entry in iterate_fasta(content, 'text'):
                names.append(entry['name'])
                seqs.append(entry['sequence'])
        else:
            names = None
            seqs = [content]

        result_lines = []
        for seq in seqs:
            sub = re.sub(r'[^ACGTURYMKSWBDHVN]', '', seq.upper())
            result_lines.append(sites2str(seq2sites(sub, what=seq_range)))

        if not valid:
            self.response.out.write('<h1>INVALID INPUT</h1>')
            self.response.out.write('%s' % problems)
        self.response.out.write('<p>action: %s</p>' % action)
        self.response.out.write('<p>format: %s</p>' % cgi.escape(self.request.get('format')))
        self.response.out.write('<p>seq_range: %s</p>' % cgi.escape(self.request.get('seq_range')))
        self.response.out.write('<p>content: %s</p>' % cgi.escape(self.request.get('content')))
        for entry in result_lines:
            self.response.out.write('<p>result: %s</p>' % entry)

class NoSuchURLHandler(webapp.RequestHandler):
    def get(self):
        _404error(self)
    
    def post(self):
        _404error(self)

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/sites2seq/(.*)', Sites2SeqHandler),
        ('/seq2sites/(.*)', Seq2SitesHandler),
        ('/.*', NoSuchURLHandler),
        ],debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()
