from flask import Flask
app = Flask(__name__)

@app.route('/foo/<xyz>')
def hello_world(xyz):
    return 'Hello, ' + xyz

if __name__ == "__main__":
    app.run(host='0.0.0.0')
