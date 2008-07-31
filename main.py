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

from mitomotifs import sites2seq
from mitomotifs import seq2sites
from mitomotifs import sites2str
from fasta import iterate_fasta
from fasta import entry2str

MAX_SEQS_SHORT  = 50
MAX_SEQS_LONG   = 20
LONG_SEQ_CUTOFF = 1500
TEMPLATES       = os.path.join(os.path.dirname(__file__), 'templates')

class Result(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

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
        format = self.request.get('format').encode('utf8')
        output = self.request.get('output').encode('utf8')
        content = self.request.get('content').encode('utf8')

        # validate submission
        problems = []
        valid = True
        if not format in ['motif_only', 'name_and_motif', 'name_n_and_motif']:
            valid = False
            problems.append('given format not one of the acceptable options.')
        if not output in ['hvr1', 'hvr2', 'hvr1and2', 'hvr1to2', 'coding', 'all']:
            valid = False
            problems.append('given output not one of the acceptable options.')

        if valid:
            content_lines = content.encode('utf8').split('\n')
            names = []
            ns = []
            motifs = []
            count = 0
            for curr_line in content_lines:
                line = re.sub(r'[,;]', ' ', curr_line)

                count += 1
                name = 'Seq%s' % count
                n = 1
                motif = line
                if format == 'name_and_motif':
                    split = line.split(' ', 1)
                    if len(split) == 2:
                        name, motif = split 
                    else:
                        valid = False
                        problems.append('The entry "%s" does not seem to be correctly formatted' % curr_line)
                elif format == 'name_n_and_motif':
                    split = line.split(' ', 2)
                    if len(split) == 3:
                        name, n, motif = split 
                        if re.match(r'^[0-9]+$', n) is None:
                            valid = False
                            problems.append("One of the given 'N's is not a number")
                        else:
                            n = int(n)
                    else:
                        valid = False
                        problems.append('The entry "%s" does not seem to be correctly formatted' % curr_line)
                names.append(name)
                ns.append(n)
                motifs.append(motif)
            
        if valid:
            pnames = []
            pseqs = []
            for name,n,motif in zip(names,ns,motifs):
                try:
                    for i in range(n):
                        pnames.append(name)
                        pseqs.append(sites2seq(motif, what=output))
                except Exception, e:
                    valid = False
                    problems.append(e)

        if not valid:
            template_values = {'problems':problems}
            path = os.path.join(TEMPLATES, 'standard_error.html')
            self.response.out.write(template.render(path, template_values))
        else:
            as_fasta = ''.join(list(entry2str({'name':name,'sequence':seq}) for name,seq in zip(pnames, pseqs)))

            template_values = {'format'     :format,
                               'results'    :as_fasta}
            path = os.path.join(TEMPLATES, 'sites2seq_result.html')
            self.response.out.write(template.render(path, template_values))

class Seq2SitesHandler(webapp.RequestHandler):
    def get(self, action):
        if action == "" or action == "main":
            template_values = {'max_long'   :MAX_SEQS_LONG,
                               'max_short'  :MAX_SEQS_SHORT,
                               'cutoff'     :LONG_SEQ_CUTOFF}
            path = os.path.join(TEMPLATES, 'seq2sites_main.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)
            
    def post(self, action):

        # get posted parameters
        content = self.request.get('content')

        # submission validation and error reporting
        problems = []
        valid = True

        # get the submitted data
        content = content.encode('utf8')

        # make sure something was submitted
        if len(content) == 0:
            valid = False
            self.redirect("/seq2sites/")

        # determine format
        format = None
        if content.startswith('>'):
            format = 'fasta'
        else:
            format = 'single_seq'
            
        # pull names and sequence out of submitted content
        names = []
        seqs = []
        if format == 'fasta':
            try:
                fnames = []
                fseqs = []
                for entry in iterate_fasta(content, 'text'):
                    fnames.append(entry['name'])
                    fseqs.append(re.sub(r'[^ACGTURYMKSWBDHVN]', '', entry['sequence'].upper()))
                names = fnames
                seqs = fseqs
            except:
                valid = False
                problems.append('There was an error in the FASTA format')
        else:
            names = ['']
            seqs = [re.sub(r'[^ACGTURYMKSWBDHVN]', '', content.upper())]

        # enforce limits for multisequence submissions
        if format == 'fasta':
            max_length = 0
            for seq in seqs:
                if len(seq) > max_length:
                    max_length = len(seq)
            if max_length <= LONG_SEQ_CUTOFF:
                if len(seqs) > MAX_SEQS_SHORT:
                    valid = False
                    problems.append('too many sequences submitted')
            elif len(seqs) > MAX_SEQS_LONG:
                valid = False
                problems.append('too many sequences submitted')

        if not valid:
            template_values = {'problems':problems}
            path = os.path.join(TEMPLATES, 'standard_error.html')
            self.response.out.write(template.render(path, template_values))
            return self.response

        result_lines = []
        for seq in seqs:
            try:
                result_lines.append(sites2str(seq2sites(seq)))
            except:
                result_lines.append('There was an error processing this sequence')

        results = list(Result(x,y) for x,y in zip(names,result_lines))
        template_values = {'format'     :format,
                           'results'    :results}
        path = os.path.join(TEMPLATES, 'seq2sites_result.html')
        self.response.out.write(template.render(path, template_values))

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
