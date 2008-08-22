#!/usr/bin/env python
#
# Copyright (c) 2008 Ryan Raaum
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 

#----------------------------------------------------------------------------#
# IMPORTS
#----------------------------------------------------------------------------#

import os
import cgi
import re
import logging
import urllib

import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from mitomotifs import sites2seq
from mitomotifs import str2sites
from mitomotifs import seq2sites
from mitomotifs import sites2str
from fasta import fasta
from fasta import entry2str

#----------------------------------------------------------------------------#
# CONSTANTS
#----------------------------------------------------------------------------#

MAX_SEQS_SHORT  = 50
MAX_SEQS_LONG   = 20
LONG_SEQ_CUTOFF = 1500
WRAP            = 70   # where to cut and wrap fasta output
TEMPLATES       = os.path.join(os.path.dirname(__file__), 'templates')

#----------------------------------------------------------------------------#
# REGEX
#----------------------------------------------------------------------------#

RE_NON_IUPAC = re.compile(r'[^ACGTURYMKSWBDHVN]')

#----------------------------------------------------------------------------#
# HANDLERS
#----------------------------------------------------------------------------#

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
        if action == "results":
            valid, template_values = process_sites2seq(self)
            if valid:
                path = os.path.join(TEMPLATES, 'sites2seq_result.html')
            else:
                path = os.path.join(TEMPLATES, 'standard_error.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)


class Seq2SitesHandler(webapp.RequestHandler):
    def get(self, action):
        if action == "" or action == "main":
            template_values = {'max_long'   :MAX_SEQS_LONG,
                               'max_short'  :MAX_SEQS_SHORT,
                               'cutoff'     :LONG_SEQ_CUTOFF,
                               'wrap'       :WRAP}
            path = os.path.join(TEMPLATES, 'seq2sites_main.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)
            
    def post(self, action):
        if action == "results":
            valid, template_values = process_seq2sites(self)
            if valid:
                path = os.path.join(TEMPLATES, 'seq2sites_result.html')
            else:
                path = os.path.join(TEMPLATES, 'standard_error.html')
            self.response.out.write(template.render(path, template_values))
        else:
            _404error(self)
                

class StaticPageHandler(webapp.RequestHandler):
    def get(self, page, action):
        template_values = {'max_long'   :MAX_SEQS_LONG,
                           'max_short'  :MAX_SEQS_SHORT,
                           'cutoff'     :LONG_SEQ_CUTOFF,
                           'wrap'       :WRAP}
        path = os.path.join(TEMPLATES, '%s.html' % page)
        self.response.out.write(template.render(path, template_values))
    
    def post(self):
        _404error(self)


class NoSuchURLHandler(webapp.RequestHandler):
    def get(self):
        _404error(self)
    
    def post(self):
        _404error(self)

#----------------------------------------------------------------------------#
# ROUTING
#----------------------------------------------------------------------------#

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/sites2seq/?(.*)', Sites2SeqHandler),
        ('/seq2sites/?(.*)', Seq2SitesHandler),
        ('/(documentation|contact)/?(.*)', StaticPageHandler),
        ('/.*', NoSuchURLHandler),
        ],debug=True)
    wsgiref.handlers.CGIHandler().run(application)

#----------------------------------------------------------------------------#
# UTILITY CLASSES
#----------------------------------------------------------------------------#

class Result(object):
    """Simple object to hold sites2seq results for template"""
    def __init__(self, name, value):
        self.name = name
        self.value = value

#----------------------------------------------------------------------------#
# PROCESSING FUNCTIONS
#----------------------------------------------------------------------------#

def process_sites2seq(handler):
    """Process data submitted in sites2seq form"""
    # get posted parameters
    format = handler.request.get('format').encode('utf8')
    output = handler.request.get('output').encode('utf8')
    content = handler.request.get('content').encode('utf8')
    add16k = handler.request.get('add16k').encode('utf8') == 'add16k'

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
                    msg = 'The entry "%s" is not correctly formatted' % curr_line
                    problems.append(msg)
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
                    msg = 'The entry "%s" is not correctly formatted' % curr_line
                    problems.append(msg)
            names.append(name)
            ns.append(n)
            motifs.append(motif)
        
    if valid:
        pnames = []
        pseqs = []
        for name,n,motif in zip(names,ns,motifs):
            try:
                sites = str2sites(motif)
                seq = sites2seq(sites, region=output, add16k=add16k)
                for i in range(n):
                    pnames.append(name)
                    pseqs.append(seq)
            except Exception, e:
                valid = False
                problems.append(e)

    if not valid:
        return (False, {'problems': problems})

    as_fasta = ''.join(list(entry2str({'name':name,'sequence':seq}, WRAP) 
                             for name,seq in zip(pnames, pseqs)))
    return (True, {'results': as_fasta})


def process_seq2sites(handler):
    """Process data submitted in seq2sites form"""
    # get posted parameters
    content = handler.request.get('content')
    wNN = handler.request.get('wNN') == 'yes'

    # submission validation and error reporting
    problems = []
    valid = True

    # get the submitted data
    content = content.encode('utf8')

    # make sure something was submitted
    if len(content) == 0:
        valid = False
        handler.redirect("/seq2sites/")

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
            for entry in fasta(content, 's'):
                fnames.append(entry['name'])
                fseqs.append(RE_NON_IUPAC.sub('', entry['sequence'].upper()))
            names = fnames
            seqs = fseqs
        except:
            valid = False
            problems.append('There was an error in the FASTA format')
    else:
        names = ['']
        seqs = [RE_NON_IUPAC.sub('', content.upper())]

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
        return (False, {'problems': problems})

    result_lines = []
    sites_by_line = []
    for seq in seqs:
        try:
            sites = seq2sites(seq)
            sites_by_line.append(sites)
            result_lines.append(sites2str(sites))
        except Exception, e:
            result_lines.append('There was an error: %s' % e)

    if wNN:
        names = ['']*len(sites_by_line)
        result_lines = []
        for sites in sites_by_line:
            curr_hvs1 = list(x for x in sites 
                             if int(x.position) in range(16023, 16570)
                             and not x.is_deletion())
            result_lines.append(sites2str(curr_hvs1))
        # un-comment the following when it is possible to POST 
        # a multipart/form-data form from google app engine
        #form_fields = {'samples': '\n'.join(hvs1_lines)}
        #form_data = urllib.urlencode(form_fields)
        #url = "http://nnhgtool.nationalgeographic.com/cgi-bin/classify/classify.ksh"
        #result = urlfetch.fetch(url=url,
        #           payload=form_data,
        #           method=urlfetch.POST,
        #           headers={'Content-Type': 'multipart/form-data'})
        #logging.info('urlfetch content: %s' % result.content)

    results = list(Result(x,y) for x,y in zip(names,result_lines))
    template_values = {'results': results}
    if wNN:
        template_values['show_note'] = 'wNN'
    return (True, template_values)

#----------------------------------------------------------------------------#
# RUN
#----------------------------------------------------------------------------#

if __name__ == '__main__':
    main()
