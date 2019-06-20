#!/usr/bin/env python

import datetime
import logging
import os.path
import time
from flask import Flask, session, request, render_template, Response, abort
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


@app.route('/two-tables')
def two_tables():
    return render_template('two-tables.html')


@app.route('/download-page')
def dload_page():
    return render_template('download.html')


@app.route('/the-download')
def download_target():
    logger = logging.getLogger('download')
    
    def chunks(end_time=20.0, size=32768):
        num = int(end_time)
        logger.info("Generating %d chunks of %.2fkb each", num, size/1024)
        n = 0
        ts = end_time / num
        with open('/dev/urandom', 'rb') as fin:
            while n < num:
                yield fin.read(size)
                n += 1
                time.sleep(ts)
        logger.info("Finished streaming, sent %.2fkb of data", (num*size)/1024)

    ret = Response(chunks(), mimetype='application/data')
    ret.headers['Content-disposition'] = 'attachment; filename="test-%d.data"' % time.time()
    return ret


@app.route('/private')
def no_login():
    abort(403)


@app.route('/broken')
def wont_work():
    raise Exception("Iz broken")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0')

