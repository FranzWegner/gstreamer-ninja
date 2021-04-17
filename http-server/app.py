from flask import Flask, request, send_from_directory
app = Flask(__name__, static_url_path='')

@app.route('/<directory>/<path:filename>', methods=["GET", "POST"])
def serve_directory(directory, filename):

    if request.method == "POST":
        #print(dir(request))
        #file = request.data
        print(filename)
        #file = request.data
        #filename = file.filename
        #file.save(filename)
        f = open(directory + "/" + filename, 'wb')
        f.write(request.data)
        f.close()


        return "POST"
    else: 
        return send_from_directory(directory, filename)