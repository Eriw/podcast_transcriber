# Podcast Episode Analyzer

A web application to search for podcast episodes, transcribe them using OpenAI's Whisper model, and generate summaries with timestamps using OpenAI.

## Features

- Search for podcast episodes
- Transcribe episodes using OpenAI's Whisper model
- Generate summaries and extract timestamps using OpenAI's text models

## Project Structure

```
transcriber/
├── backend/             # FastAPI backend
│   ├── main.py          # Main FastAPI application
│   ├── requirements.txt # Python dependencies
│   └── .env.sample      # Sample environment variables (copy to .env)
├── frontend/            # Frontend web application
│   ├── index.html       # HTML structure
│   ├── styles.css       # CSS styling
│   └── app.js           # JavaScript functionality
└── README.md            # This file
```

## Setup

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Create an environment file:
   ```
   cp .env.sample .env
   ```

5. Edit the `.env` file and add your OpenAI API key:
   - Get an OpenAI API key from https://platform.openai.com/

### Frontend Setup

The frontend is a simple HTML/CSS/JavaScript application. No additional setup is required.

## Running the Application

1. Start the backend server:
   ```
   cd backend
   python main.py
   ```
   The server will start at http://localhost:8000

2. Open the frontend:
   - Option 1: Open the `frontend/index.html` file directly in your browser
   - Option 2: Use a simple HTTP server:
     ```
     cd frontend
     python -m http.server
     ```
     Then visit http://localhost:8000 in your browser

## API Endpoints

- `GET /api/search?query={query}`: Search for podcast episodes
- `POST /api/transcribe`: Transcribe a podcast episode using OpenAI's Whisper (requires `audio_url` in request body)
- `POST /api/summarize`: Generate a summary with timestamps (requires `transcript` in request body)

## Notes

- The search endpoint currently returns dummy data. You can integrate a real podcast search API.
- Transcription uses OpenAI's Whisper model which requires downloading the audio file temporarily.
- The OpenAI API requires a valid API key and may incur costs depending on usage.
- Whisper is optimized for transcribing speech to text and performs well on podcast audio.

## License

MIT 