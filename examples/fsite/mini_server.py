#!/usr/bin/env python3

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

def chunks(end_time=20.0, size=32768):
    logger = logging.getLogger('download')
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


@app.route('/the-download')
def download_target():
    ret = Response(chunks(), mimetype='application/data')
    ret.headers['Content-disposition'] = 'attachment; filename="test-%d.data"' % time.time()
    return ret

@app.route('/the-download/fixed')
def download_target2():
    ret = Response(chunks(end_time=5.0), mimetype='application/data')
    ret.headers['Content-disposition'] = 'attachment; filename="test.data"'
    return ret


@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    logger = logging.getLogger('upload')
    if request.method == 'GET':
        return render_template('upload.html')

    # POST, consume uploaded file

    if 'file' not in request.files:
        logger.warning("Uploaded form did not contain 'file'")
        return render_template('upload.html')
    ufile = request.files['file']
    if not ufile.filename:
        logger.warning("No file selected")
        return render_template('upload.html')
    payload = ufile.read(200)
    ufile.close()
    logger.info("Got a file %s(%d): %s", ufile.filename, len(payload), ufile.mimetype)
    return render_template('upload-ok.html', file=ufile, payload=payload)


@app.route('/long-table/<sub>')
def long_tbl1(sub=None):
    cols = ['id', 'Name', 'Cell', 'Date', 'Amount']
    lim = int(request.args.get('limit', 10))
    def source(limit=1000):
        i = 0
        d = datetime.datetime.now()
        while i < limit:
            yield i, 'Foo %x' % i, 'C%d' % i, d, 0.4 * i
            d += datetime.timedelta(hours=6)
            i += 1
    return render_template('long-table.html', columns=cols, data=source(limit=lim))


@app.route('/rich-form')
@app.route('/rich-form2')
def rich_form():
    return render_template('rich-form.html')


@app.route('/private')
def no_login():
    abort(403)


@app.route('/broken')
def wont_work():
    raise Exception("Iz broken")


@app.route('/bad-link')
def run_tmpl2():

    return render_template('bad-link.html')

@app.route('/bad-js')
def run_tmpl3():
    return render_template('bad-js.html')


@app.route('/alerts')
def do_alerts():
    return render_template('alerts.html')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0')

