#!/usr/bin/env python

import datetime
import logging
import os.path
from flask import Flask, session, request, render_template
from server_sessions import ManagedSessionInterface, CachingSessionManager, FileBackedSessionManager

app = Flask(__name__)
app.secret_key = '90m12iu0x7msadkj9bsoads8t53dbcxviorbscjvoiewr'
skip_paths = ()
CACHE_DIR = os.path.expanduser('~/.cache/fsite-server')

app.session_interface = ManagedSessionInterface(CachingSessionManager(
                            FileBackedSessionManager(CACHE_DIR, app.secret_key),
                            50), skip_paths, datetime.timedelta(days=1))


@app.route('/', methods=['GET', 'POST'])
def run():
    if request.method == 'POST':
        session['number'] = request.form['number']

    return render_template('index.html', number=session.get('number', ''))


@app.route('/samba', methods=['GET',])
def dsmb():
    return render_template('smb.html')


@app.route('/template', methods=['GET', 'POST'])
def run_tmpl():

    return render_template('template_test.html')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0')

