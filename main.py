from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/gpt', methods=['POST'])
def gpt():
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"answer": "No llegaron datos al backend. Revisa el JSON del frontend."}), 400
    mensaje = data.get("message", "")
    tema = data.get("tema", "")
    return jsonify({"answer": f"Hola, recibí: '{mensaje}' en el tema '{tema}'."})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000)
