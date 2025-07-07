import os
import requests
import base64
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import json # Import json for embedding data in HTML

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'} # Added webp just in case

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Get Fashn.ai API key from environment variable
FASHN_API_KEY = os.getenv('FASHN_API_KEY')
API_KEY_MISSING = not FASHN_API_KEY or FASHN_API_KEY == 'your_api_key_here' # Flag for easier check

if API_KEY_MISSING:
    print("WARNING: Missing or invalid Fashn.ai API key. API calls will fail.")

FASHN_API_URL = "https://api.fashn.ai/v1/run"
FASHN_STATUS_URL = "https://api.fashn.ai/v1/status/" # Base URL for status checks

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_base64_encoded_image(image_path):
    """Convert an image file to base64 encoding"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None

@app.route('/')
def index():
    """Render the main page, passing structured clothing data"""
    clothing_base_dir = os.path.join('static', 'clothing')
    genders = ['male', 'female']
    clothing_data = {}

    for gender in genders:
        gender_dir = os.path.join(clothing_base_dir, gender)
        if os.path.isdir(gender_dir):
            items = [f for f in os.listdir(gender_dir)
                     if os.path.isfile(os.path.join(gender_dir, f)) and allowed_file(f)]
            # Store items with the gender prefix needed for the path
            clothing_data[gender] = [os.path.join(gender, item).replace("\\", "/") for item in items] # Store relative path like "male/item.jpg"
        else:
            clothing_data[gender] = []
            print(f"Warning: Directory not found: {gender_dir}")

    api_key_status = "Missing" if API_KEY_MISSING else "OK"

    # Convert clothing_data to JSON to safely embed in HTML/JS
    clothing_data_json = json.dumps(clothing_data)

    return render_template('index.html',
                           clothing_data_json=clothing_data_json,
                           api_key_status=api_key_status)

@app.route('/api/try-on', methods=['POST'])
def try_on():
    """Handle try-on requests to Fashn.ai API"""
    if API_KEY_MISSING:
        return jsonify({'error': 'API key is missing or invalid. Please check server configuration.'}), 400

    if 'person_image' not in request.files:
        return jsonify({'error': 'No person image provided'}), 400

    person_image = request.files['person_image']
    # garment_id now includes gender path, e.g., "male/kurta1.jpg"
    garment_id = request.form.get('garment_id')

    if not garment_id:
        return jsonify({'error': 'No garment selected'}), 400

    if not person_image or not allowed_file(person_image.filename):
         return jsonify({'error': 'Invalid or missing person image file'}), 400

    # Save person image temporarily
    person_filename = secure_filename(f"user_{person_image.filename}") # Add prefix to avoid conflicts
    person_path = os.path.join(app.config['UPLOAD_FOLDER'], person_filename)
    try:
        person_image.save(person_path)
    except Exception as e:
        print(f"Error saving uploaded file: {e}")
        return jsonify({'error': 'Failed to save uploaded image'}), 500

    # Construct full garment path using the garment_id which includes the subdirectory
    # garment_id = "male/kurta1.jpg" -> garment_path = "static/clothing/male/kurta1.jpg"
    garment_path = os.path.join('static', 'clothing', garment_id)

    if not os.path.exists(garment_path):
        print(f"Error: Garment file not found at resolved path: {garment_path} (from garment_id: {garment_id})")
        # Clean up uploaded file before returning error
        if os.path.exists(person_path):
            os.remove(person_path)
        return jsonify({'error': 'Selected garment not found on server'}), 404

    person_base64 = get_base64_encoded_image(person_path)
    garment_base64 = get_base64_encoded_image(garment_path)

    # Clean up temporary file *after* encoding
    if os.path.exists(person_path):
        os.remove(person_path)

    if not person_base64 or not garment_base64:
        return jsonify({'error': 'Failed to process images'}), 500

    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {FASHN_API_KEY}'
        }

        # Category detection (can be refined, maybe use gender info if needed)
        filename_lower = os.path.basename(garment_id).lower() # Use only filename for keyword check
        if any(keyword in filename_lower for keyword in ['shirt', 'top', 'blouse', 'sweater', 'jacket', 'kurta']):
            category = 'tops'
        elif any(keyword in filename_lower for keyword in ['pant', 'trouser', 'jean', 'skirt']):
            category = 'bottoms'
        elif any(keyword in filename_lower for keyword in ['dress', 'jumpsuit', 'romper', 'gown']):
            category = 'one-pieces'
        else:
            category = 'auto'

        payload = {
            'model_image': f'data:image/jpeg;base64,{person_base64}',
            'garment_image': f'data:image/jpeg;base64,{garment_base64}',
            'category': 'one-pieces',
            'mode': 'quality',
            #'restore_background': True,
            #'garment_photo_type': 'model'
        }

        response = requests.post(FASHN_API_URL, headers=headers, json=payload, timeout=30) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        result = response.json()

        # Standardize response: Always return prediction_id if available for polling
        if 'id' in result:
            # Return prediction_id for polling, regardless of initial status
             return jsonify({'prediction_id': result['id'], 'status': result.get('status', 'processing')})
        # Handle potential immediate results (less likely with this API structure)
        elif 'output' in result and result['output']:
             return jsonify({'image_urls': result['output'], 'status': 'completed'})
        else:
             # If no ID and no output, it's likely an error or unexpected format
             print("Unexpected API response format:", result)
             return jsonify({'error': 'Unexpected response from try-on service'}), 500

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return jsonify({'error': f'Failed to connect to try-on service: {e}'}), 503 # Service Unavailable
    except Exception as e:
        print(f"Server Error during try-on: {e}")
        return jsonify({'error': f'An internal server error occurred: {str(e)}'}), 500

@app.route('/api/check-status/<prediction_id>', methods=['GET'])
def check_status(prediction_id):
    """Check the status of a prediction"""
    if API_KEY_MISSING:
         return jsonify({'error': 'API key is missing or invalid.'}), 400
    if not prediction_id:
         return jsonify({'error': 'Missing prediction ID.'}), 400

    try:
        headers = {'Authorization': f'Bearer {FASHN_API_KEY}'}
        status_url = f"{FASHN_STATUS_URL}{prediction_id}"

        response = requests.get(status_url, headers=headers, timeout=15) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses

        result = response.json()

        # Standardize successful completion response for frontend
        if 'status' in result and (result['status'] == 'completed' or result['status'] == 'succeeded') and 'output' in result:
             # Rename 'output' to 'image_urls' for frontend consistency
            result['image_urls'] = result['output']
            # Ensure status is set to 'completed' for frontend check
            result['status'] = 'completed'

        return jsonify(result)

    except requests.exceptions.RequestException as e:
        print(f"API Status Check Error: {e}")
        # Don't treat temporary network errors as prediction failure, let frontend retry
        return jsonify({'error': f'Failed to check status: {e}', 'status': 'polling_error'}), 503
    except Exception as e:
        print(f"Server Error during status check: {e}")
        return jsonify({'error': f'An internal server error occurred during status check: {str(e)}'}), 500

if __name__ == '__main__':
    # Use environment variable for port, default to 5000
    #port = int(os.environ.get('PORT', 5005))
    # Set debug=False for production environments
    app.run(host='0.0.0.0', port=5005, ssl_context=("cert.pem", "key.pem"))