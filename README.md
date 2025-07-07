# Virtual Try-On Web App

A fullscreen touchscreen application for retail stores that allows customers to virtually try on clothing items using AI-powered image generation technology.

## Features

- Welcome screen with rotating fashion previews
- Interactive try-on experience with real-time clothing overlay
- "Complete the look" accessory suggestions
- Simple, intuitive touch interface designed for in-store kiosks

## Setup and Installation

### Prerequisites

- Python 3.8 or higher
- A Fashn.ai API key (https://fashn.ai)

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd virtual-tryon
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

3. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure your environment:
   - Copy `.env.example` to `.env` (or use the existing one)
   - Add your Fashn.ai API key to the `.env` file:
     ```
     FASHN_API_KEY=your_api_key_here
     ```

5. Add clothing images:
   - Place clothing item images in the `static/clothing` directory
   - Place accessory images in the `static/images` directory

## Running the Application

Start the Flask server:
```
python app.py
```

The application will be available at http://localhost:5000

## Deployment

For production use:
1. Use a production WSGI server (Gunicorn, uWSGI, etc.)
2. Set `debug=False` in app.py
3. Consider using a reverse proxy (Nginx, Apache) for better performance
4. Configure the server to run in kiosk/fullscreen mode

## Project Structure

```
/virtual-tryon
├── /static                  # Static assets
│   ├── /images              # Model preview images and accessories
│   ├── /clothing            # Garment images for try-on
│   └── /uploads             # Temporary storage for uploaded user photos
├── /templates
│   └── index.html           # Main application template (includes both screens)
├── app.py                   # Flask application logic
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Fashn.ai API Integration

The application uses the Fashn.ai API to generate try-on images. The API endpoint used is `/tryon/`, which accepts:
- A user photo image
- A garment image

The API returns URLs to generated try-on images that are displayed in the application.

## Environment Configuration

The backend relies on a single environment variable:

| Variable | Purpose | Required | Example |
|----------|---------|----------|---------|
| `FASHN_API_KEY` | Bearer token used to authenticate against the Fashn.ai REST API | **Yes** | `sk_live_...` |

Create a `.env` file at the project root and add:

```env
FASHN_API_KEY=sk_live_your_token
```

`python-dotenv` is loaded automatically, so running `python app.py` will pick up the key from `.env`.

> Without a valid key the server still starts but all `/api/*` routes will return 400 with an error message.

## Running Locally (HTTP)

If you just want to test locally without HTTPS you can comment out the `ssl_context` line at the bottom of `app.py` and run:

```bash
python app.py  # now listens on http://127.0.0.1:5005
```

## Running Locally (HTTPS / Kiosk Mode)

The default `app.py` enables HTTPS using `cert.pem` / `key.pem` so browsers treat the kiosk as secure.  
Generate a self-signed certificate (good for 365 days):

```bash
openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes \
  -keyout key.pem -out cert.pem \
  -subj "/C=US/ST=CA/L=San Francisco/O=Retail/Kiosk/CN=localhost"
```

Then start the server:

```bash
python app.py  # https://localhost:5005
```

## Backend REST API

| Verb | Endpoint | Body / Params | Description |
|------|----------|---------------|-------------|
| POST | `/api/try-on` | multipart-form with `person_image` file & `garment_id` string | Initiates an asynchronous try-on request. Returns `{prediction_id, status}` on success. |
| GET  | `/api/check-status/<prediction_id>` | – | Polls the Fashn.ai service and returns `{status, image_urls}` when finished. |

Status values: `processing`, `completed`, `succeeded`, `failed`, `polling_error`.

## Typical Frontend Flow

1. User selects a garment thumbnail in the gallery (gender-segmented).
2. User uploads their photo via the file picker (captured with a kiosk camera or touchscreen).
3. JavaScript sends `POST /api/try-on` → receives `prediction_id`.
4. Frontend polls `GET /api/check-status/<prediction_id>` every few seconds until `status === 'completed'`.
5. Returned `image_urls` are displayed in place for the user to swipe through.

All client-side logic lives in `templates/index.html`.

## Developer Workflow

```bash
# create virtualenv
python -m venv venv && source venv/bin/activate

# install deps
pip install -r requirements.txt

# run linting
pip install black flake8
black app.py
flake8
```



## Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|------------|
| `WARNING: Missing or invalid Fashn.ai API key` | `FASHN_API_KEY` not set or incorrect | Define key in `.env` or environment | 
| 503 from `/api/try-on` | Network/time-out to Fashn.ai | Check internet, confirm API reachability | 
| Images not displayed | Frontend polling stops <br> or `status` never becomes `completed` | Inspect browser console & server logs, verify `prediction_id` exists | 

## License

[Your License Here]
