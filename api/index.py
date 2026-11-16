# -*- coding: utf-8 -*-
import os
import sys
import io
import json
import urllib.parse
from email.message import Message

# Ensure root directory is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import QuizRequestHandler

class handler(QuizRequestHandler):
    """Native Vercel BaseHTTPRequestHandler entrypoint"""
    pass

class WSGIAdapter(QuizRequestHandler):
    """Adapter allowing QuizRequestHandler to run cleanly as a WSGI application"""
    def __init__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET').upper()
        path = environ.get('PATH_INFO', '')
        query_string = environ.get('QUERY_STRING', '')
        if query_string:
            path = f'{path}?{query_string}'

        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        except Exception:
            content_length = 0

        body = b''
        if content_length > 0 and 'wsgi.input' in environ:
            try:
                body = environ['wsgi.input'].read(content_length)
            except Exception:
                body = b''

        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()

        msg = Message()
        if content_length > 0:
            msg['Content-Length'] = str(content_length)
        if 'CONTENT_TYPE' in environ:
            msg['Content-Type'] = environ['CONTENT_TYPE']
        for k, v in environ.items():
            if k.startswith('HTTP_'):
                header_name = k[5:].replace('_', '-').title()
                msg[header_name] = v

        self.headers = msg
        self.path = path
        self.command = method
        self.requestline = f'{method} {path} HTTP/1.1'
        self.client_address = ('127.0.0.1', 8000)
        self.request_version = 'HTTP/1.1'
        self.close_connection = True

        try:
            if method == 'GET':
                self.do_GET()
            elif method == 'POST':
                self.do_POST()
            elif method == 'OPTIONS':
                self.do_OPTIONS()
            elif method == 'DELETE':
                self.do_DELETE()
            else:
                self.send_error(405, 'Method Not Allowed')
        except Exception as e:
            self._send_error(f"Internal server error: {str(e)}", 500)

        raw_output = self.wfile.getvalue()
        header_end = raw_output.find(b'\r\n\r\n')
        if header_end != -1:
            header_bytes = raw_output[:header_end].decode('latin-1')
            response_body = raw_output[header_end + 4:]
            lines = header_bytes.split('\r\n')
            status_line = lines[0]
            status = status_line.split(' ', 1)[1] if ' ' in status_line else '200 OK'
            headers = []
            for line in lines[1:]:
                if ': ' in line:
                    hk, hv = line.split(': ', 1)
                    headers.append((hk, hv))
            start_response(status, headers)
            self.response = [response_body]
        else:
            start_response('200 OK', [('Content-Type', 'application/json')])
            self.response = [raw_output]

def app(environ, start_response):
    """Native Vercel WSGI entrypoint"""
    adapter = WSGIAdapter(environ, start_response)
    return adapter.response
