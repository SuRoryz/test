import git
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from unidiff import PatchSet
import os
from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
socketio = SocketIO(app=app, cors_allowed_origins='*')

REPO = None
CURRENT_FILENAME = None

@socketio.on('oswalk')
def oswalk(data):
    path = os.path.abspath(os.sep)
    
    if "path" in data:
        path = data['path']

    dirs = []
    files = []

    a = os.listdir(path)

    for file in a:
        if os.path.isdir(os.path.join(path, file)):
            dirs.append(file)
        else:
            files.append(file)
    
    emit('oswalk', {"path": os.path.abspath(path), "dirs": dirs, "files": files})

@socketio.on('setrepo')
def setrepo(data):
    global REPO
    REPO = Repository(data['path'], diffCallback=emitDiffs)

    emit("setrepo")

def emitDiffs(REPO):
    global CURRENT_FILENAME

    socketio.emit('getdiffs', {"data": REPO.getDiffForFile(REPO.getDiffbyFilename(CURRENT_FILENAME))})

@socketio.on('getdiffs')
def setrepo(data):
    global CURRENT_FILENAME
    global REPO
    
    filename = data["filename"]

    chunk = REPO.getDiffForFile(REPO.getDiffbyFilename(filename))
    CURRENT_FILENAME = filename

    emit('getdiffs', {"data": chunk})

@app.route("/getfile", methods=['POST'])
def getfile():
    data = request.json
    print(data)
    path = data['path']

    print(os.path.abspath(path))

    return send_file(os.path.abspath(path))

@app.route("/savefile", methods=['POST'])
def savefile():
    data = request.json
    path = data['path']

    with open(os.path.abspath(path), 'w') as f:
        f.write(data['data'])

    return 'ok'

class RepoEventHandler(FileSystemEventHandler):
    def __init__(self, repository):
        super().__init__()

        self.repository = repository

    def on_any_event(self, event):
        print(event)
        self.repository.updateDiffs()
        self.repository.diffCallback(self.repository)

class Repository:
    def __init__(self, name: str = None, url: str = None, diffCallback = None):
        if url:
            try:
                self.name = url
            except:
                pass
        
        self.name = name

        self.r = git.Repo(self.name)
        self.diffs = []

        self.observer = None
        self.diffCallback = diffCallback

        self.updateDiffs()
        self.addRepoObserver()
    
    def updateDiffs(self):
        self.diffs = self.r.index.diff(None, create_patch=True, ignore_space_at_eol=True)
    
    def addRepoObserver(self):
        if self.observer:
            self.observer.stop()
        
        event_handler = RepoEventHandler(self)

        self.observer = Observer()
        self.observer.schedule(event_handler, self.name, recursive=True)
        self.observer.start()
    
    def getDiffbyFilename(self, filename):
        for d in self.diffs:
            if d.a_rawpath.decode('utf-8') == filename:
                return d
    
    def getDiffForFile(self, d):
        result_chunk = []

        a_path = "--- " + d.a_rawpath.decode('utf-8')
        b_path = "+++ " + d.b_rawpath.decode('utf-8')

        print(d.diff)

        patch = PatchSet(a_path + os.linesep + b_path + os.linesep + d.diff.decode('utf-8'))
        for h in patch[0]:
            for l in h:
                ind = l.target_line_no if l.target_line_no else l.source_line_no

                if not ind:
                    continue

                result_chunk.append( {"index": ind, "value": l.value, "type": "+" if l.is_added else "-" if l.is_removed else ""} )

        return result_chunk

    
    def createDiffChunk(self):
        result_chunk = []

        for d in self.diffs:
            a_path = "--- " + d.a_rawpath.decode('utf-8')
            b_path = "+++ " + d.b_rawpath.decode('utf-8')
            patch = PatchSet(a_path + os.linesep + b_path + os.linesep + d.diff.decode('utf-8'))
            for h in patch[0]:
                for l in h:
                    ind = l.target_line_no if l.target_line_no else l.source_line_no

                    if not ind:
                        continue

                    result_chunk.append( {"index": ind, "value": l.value, "type": "+" if l.is_added else "-" if l.is_removed else ""} )

        return result_chunk

if __name__ == '__main__':
    socketio.run(app)