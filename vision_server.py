from flask import Flask, request, jsonify
from flask_cors import CORS
from test_end_to_end import analyze_image_with_gemini
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/vision', methods=['POST'])
def vision():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
        
    file = request.files['image']
    filepath = "temp_upload.png"
    file.save(filepath)
    
    try:
        print(f"Analyzing {filepath} with Gemini Vision API...")
        res = analyze_image_with_gemini(filepath)
        return jsonify(res)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Vision API Backend running on port 5001...")
    app.run(port=5001, debug=False)
