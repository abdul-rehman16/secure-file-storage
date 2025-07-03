import os

from flask import Flask, render_template, request,redirect,url_for

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    files = os.listdir(UPLOAD_FOLDER)
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    if file and file.filename != '':
        #TODO: Update the file save to azure code
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run(debug=True)



