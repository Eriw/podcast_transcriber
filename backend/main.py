import os
import time
import requests
import traceback
from fastapi import FastAPI, HTTPException, File, UploadFile, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import openai
from dotenv import load_dotenv
import json
import sys
from typing import Optional, List, Dict, Any
import tempfile
import subprocess
import shutil
from pathlib import Path
import math

# Import our iTunes API module
from itunes_api import search_itunes, format_podcast_results

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the OpenAI API key is set
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print(f"API Key available: {OPENAI_API_KEY is not None}")
if OPENAI_API_KEY:
    # Only show the first few characters for security
    masked_key = OPENAI_API_KEY[:4] + "*" * (len(OPENAI_API_KEY) - 8) + OPENAI_API_KEY[-4:] if len(OPENAI_API_KEY) > 8 else "***"
    print(f"API Key (masked): {masked_key}")
openai.api_key = OPENAI_API_KEY

# --- Podcast Search Endpoint ---
# For now we return dummy data. Later, you can integrate a real podcast search API.
@app.get("/api/search")
def search_podcasts(query: str):
    dummy_data = [
        {
            "title": "Episode 1: Summary from Feb 27, 2025",
            "description": "A podcast episode summary from February 27",
            "audio_url": "http://wirebrand.se/podcast/2025-02-27_summary.mp3"
        },
        {
            "title": "Episode 2: Summary from Feb 26, 2025",
            "description": "A podcast episode summary from February 26",
            "audio_url": "http://wirebrand.se/podcast/2025-02-26_summary.mp3"
        },
    ]
    # Simple filter by query (case-insensitive)
    results = [
        episode for episode in dummy_data
        if query.lower() in episode["title"].lower() or query.lower() in episode["description"].lower()
    ]
    return results

# --- iTunes Podcast Search Endpoints ---
@app.get("/api/itunes/podcasts")
def search_itunes_podcasts(
    query: str,
    limit: int = Query(10, ge=1, le=200),
    country: str = Query("US", min_length=2, max_length=2)
):
    """
    Search for podcasts in the iTunes database.
    
    Args:
        query: Search term
        limit: Maximum number of results (1-200)
        country: Two-letter country code
        
    Returns:
        Formatted list of podcasts matching the search criteria
    """
    # Call the iTunes API with podcast entity
    results = search_itunes(
        query=query,
        media="podcast",
        entity="podcast",
        limit=limit,
        country=country
    )
    
    # Check for errors in the response
    if "error" in results:
        raise HTTPException(status_code=500, detail=results["error"])
    
    # Format the results for our application
    formatted_results = format_podcast_results(results)
    
    return formatted_results

@app.get("/api/itunes/episodes")
def search_itunes_episodes(
    query: str,
    limit: int = Query(10, ge=1, le=200),
    country: str = Query("US", min_length=2, max_length=2),
    podcast_id: Optional[int] = None
):
    """
    Search for podcast episodes in the iTunes database.
    
    Args:
        query: Search term
        limit: Maximum number of results (1-200)
        country: Two-letter country code
        podcast_id: Optional ID of a specific podcast to search within
        
    Returns:
        Formatted list of podcast episodes matching the search criteria
    """
    # Prepare additional parameters if needed
    additional_params = {}
    
    # When searching for episodes of a specific podcast
    if podcast_id:
        additional_params["collectionId"] = podcast_id
        
        # If no query is provided but we have a podcast_id, use a wildcard search
        # This helps find all episodes for a podcast
        if not query or query.strip() == "":
            query = "*"  # Use wildcard to match all episodes
    
    # Call the iTunes API with podcastEpisode entity
    results = search_itunes(
        query=query,
        media="podcast",
        entity="podcastEpisode",
        limit=limit,
        country=country,
        additional_params=additional_params
    )
    
    # Check for errors in the response
    if "error" in results:
        raise HTTPException(status_code=500, detail=results["error"])
    
    # Format the results for our application
    formatted_results = format_podcast_results(results)
    
    return formatted_results

# --- Audio Processing Functions ---
def check_ffmpeg_installed():
    """Check if FFmpeg is installed on the system."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print("FFmpeg is not installed or not in PATH")
        return False

def split_audio_file_python(input_file, output_dir, max_size_mb=20):
    """
    Split an audio file into smaller chunks using Python's built-in file operations.
    This is a fallback method when FFmpeg is not available.
    
    Args:
        input_file: Path to the input audio file
        output_dir: Directory to save the chunks
        max_size_mb: Maximum size of each chunk in MB (default: 20MB)
        
    Returns:
        List of paths to the chunk files
    """
    print("Using Python fallback method to split audio file")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get file size
    file_size = os.path.getsize(input_file)
    file_size_mb = file_size / (1024 * 1024)
    
    # Calculate chunk size in bytes (slightly less than max_size_mb to be safe)
    chunk_size = int(max_size_mb * 0.95 * 1024 * 1024)
    
    # Calculate number of chunks
    num_chunks = math.ceil(file_size / chunk_size)
    print(f"Splitting {file_size_mb:.2f} MB file into {num_chunks} chunks of ~{max_size_mb} MB each")
    
    chunk_files = []
    
    # Read the input file and split it
    with open(input_file, 'rb') as f:
        for i in range(num_chunks):
            output_file = os.path.join(output_dir, f"chunk_{i:03d}.mp3")
            
            # Read a chunk of data
            data = f.read(chunk_size)
            
            # Write the chunk to a new file
            with open(output_file, 'wb') as chunk_f:
                chunk_f.write(data)
            
            chunk_size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"Created chunk {i+1}/{num_chunks}: {output_file} ({chunk_size_mb:.2f} MB)")
            
            chunk_files.append(output_file)
    
    return chunk_files

def split_audio_file(input_file, output_dir, chunk_duration_seconds=600, max_size_mb=20):
    """
    Split an audio file into smaller chunks using FFmpeg.
    Falls back to a Python-based method if FFmpeg is not available.
    
    Args:
        input_file: Path to the input audio file
        output_dir: Directory to save the chunks
        chunk_duration_seconds: Duration of each chunk in seconds (default: 10 minutes)
        max_size_mb: Maximum size of each chunk in MB (default: 20MB)
        
    Returns:
        List of paths to the chunk files
    """
    # Check if FFmpeg is installed
    if not check_ffmpeg_installed():
        print("FFmpeg not available, using Python fallback method")
        return split_audio_file_python(input_file, output_dir, max_size_mb)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get audio file duration using FFmpeg
    duration_cmd = [
        "ffmpeg", "-i", input_file, 
        "-hide_banner", "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1"
    ]
    
    try:
        result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        print(f"Audio duration: {duration} seconds")
    except subprocess.SubprocessError as e:
        print(f"Error getting audio duration: {str(e)}")
        # If we can't get the duration, use file size to estimate chunks
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        num_chunks = max(1, int(file_size_mb / max_size_mb) + 1)
        duration = num_chunks * chunk_duration_seconds
        print(f"Estimated duration based on file size: {duration} seconds")
    
    # Calculate number of chunks
    num_chunks = max(1, int(duration / chunk_duration_seconds) + 1)
    print(f"Splitting into {num_chunks} chunks")
    
    chunk_files = []
    
    # Split the file into chunks
    for i in range(num_chunks):
        start_time = i * chunk_duration_seconds
        output_file = os.path.join(output_dir, f"chunk_{i:03d}.mp3")
        
        # FFmpeg command to extract a chunk
        cmd = [
            "ffmpeg", "-i", input_file,
            "-ss", str(start_time),
            "-t", str(chunk_duration_seconds),
            "-c:a", "libmp3lame",  # Use MP3 codec
            "-b:a", "128k",        # Reduce bitrate to keep file size down
            "-ac", "1",            # Convert to mono
            output_file
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            
            # Check if the output file exists and has content
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                chunk_files.append(output_file)
                print(f"Created chunk {i+1}/{num_chunks}: {output_file}")
            else:
                print(f"Chunk {i+1}/{num_chunks} is empty or not created")
                
        except subprocess.SubprocessError as e:
            print(f"Error creating chunk {i+1}: {str(e)}")
            # If this is the last chunk and it failed, it might be because we're past the end of the file
            if i < num_chunks - 1:
                raise Exception(f"Failed to split audio file: {str(e)}")
    
    return chunk_files

async def transcribe_audio_chunk(chunk_file):
    """
    Transcribe a single audio chunk using OpenAI's Whisper API.
    
    Args:
        chunk_file: Path to the audio chunk file
        
    Returns:
        Transcription text
    """
    print(f"Transcribing chunk: {chunk_file}")
    
    try:
        # Get OpenAI library version
        try:
            openai_version = openai.__version__
            print(f"OpenAI library version: {openai_version}")
        except AttributeError:
            print("OpenAI library version unknown")
        
        transcript_text = ""
        
        # First try using the newer client method
        try:
            print("Attempting transcription with newer OpenAI client...")
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            with open(chunk_file, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            transcript_text = response.text
            print(f"Transcription successful with new API. Length: {len(transcript_text)} chars")
            
        except (ImportError, AttributeError, Exception) as e:
            print(f"New API failed: {str(e)}")
            print("Falling back to legacy API...")
            
            # Fall back to legacy API
            try:
                with open(chunk_file, "rb") as audio_file:
                    audio_file_data = audio_file.read()
                
                # Try direct API call
                files = {
                    'file': ('audio.mp3', audio_file_data),
                    'model': (None, 'whisper-1')
                }
                headers = {
                    'Authorization': f'Bearer {OPENAI_API_KEY}'
                }
                
                print("Calling OpenAI API directly...")
                api_response = requests.post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    headers=headers,
                    files=files
                )
                
                if api_response.status_code == 200:
                    result = api_response.json()
                    transcript_text = result.get('text', '')
                    print(f"Direct API call successful. Length: {len(transcript_text)} chars")
                else:
                    print(f"API call failed: {api_response.status_code}")
                    print(f"Response: {api_response.text}")
                    raise Exception(f"API call failed: {api_response.status_code} - {api_response.text}")
                
            except Exception as e:
                print(f"Direct API call failed: {str(e)}")
                raise
        
        return transcript_text
        
    except Exception as e:
        print(f"Error transcribing chunk {chunk_file}: {str(e)}")
        raise

# --- Transcription Endpoint ---
class TranscriptionRequest(BaseModel):
    audio_url: str

@app.post("/api/transcribe")
async def transcribe_podcast(request: TranscriptionRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    temp_audio_path = "temp_audio.mp3"
    temp_dir = None
    
    try:
        # Download the audio file from the URL
        print(f"Downloading audio from: {request.audio_url}")
        
        # Check if the URL is valid and accessible
        try:
            audio_response = requests.get(request.audio_url, stream=True, timeout=30)
            audio_response.raise_for_status()  # Will raise an exception for HTTP errors
        except requests.exceptions.RequestException as e:
            print(f"Error accessing URL: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error accessing audio URL: {str(e)}")
        
        # Create a temporary file for the downloaded audio
        try:
            with open(temp_audio_path, 'wb') as f:
                for chunk in audio_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(temp_audio_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"Audio file downloaded to: {temp_audio_path}, Size: {file_size_mb:.2f} MB")
            
            if file_size == 0:
                raise HTTPException(status_code=500, detail="Downloaded audio file is empty")
                
            # Check if file size exceeds OpenAI's limit (25MB)
            if file_size > 25 * 1024 * 1024:  # 25MB in bytes
                print(f"Audio file too large: {file_size_mb:.2f} MB - will split into chunks")
                
                # Create a temporary directory for the chunks
                temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")
                print(f"Created temporary directory for chunks: {temp_dir}")
                
                try:
                    # Split the audio file into chunks
                    chunk_files = split_audio_file(
                        temp_audio_path, 
                        temp_dir,
                        chunk_duration_seconds=300,  # 5 minutes per chunk
                        max_size_mb=20              # 20MB max per chunk
                    )
                    
                    if not chunk_files:
                        raise Exception("Failed to split audio file into chunks")
                    
                    print(f"Split audio into {len(chunk_files)} chunks")
                    
                    # Transcribe each chunk
                    transcripts = []
                    for chunk_file in chunk_files:
                        chunk_transcript = await transcribe_audio_chunk(chunk_file)
                        transcripts.append(chunk_transcript)
                    
                    # Combine the transcripts
                    full_transcript = " ".join(transcripts)
                    print(f"Combined transcript length: {len(full_transcript)} chars")
                    
                    # Clean up
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
                        print("Removed original audio file")
                    
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"Removed temporary directory: {temp_dir}")
                        temp_dir = None
                    
                    return {"transcript": full_transcript}
                    
                except Exception as e:
                    print(f"Error processing chunks: {str(e)}")
                    raise Exception(f"Error processing audio chunks: {str(e)}")
                
            else:
                # File is small enough to transcribe directly
                print("File is within size limits, transcribing directly")
                transcript_text = await transcribe_audio_chunk(temp_audio_path)
                
                # Clean up
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                    print("Temporary file removed")
                
                return {"transcript": transcript_text}
                
        except IOError as e:
            print(f"I/O error writing audio file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error saving audio file: {str(e)}")
    
    except HTTPException:
        # Clean up temp files if they exist
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                print("Cleaned up temp audio file after HTTP exception")
            except:
                pass
        
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory after HTTP exception: {temp_dir}")
            except:
                pass
        
        # Re-raise the HTTP exception
        raise
        
    except Exception as e:
        # Ensure temp files are cleaned up
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                print("Cleaned up temp audio file after error")
            except:
                pass
        
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory after error: {temp_dir}")
            except:
                pass
        
        # Capture the full stack trace
        trace = traceback.format_exc()
        print(f"Error processing request: {str(e)}")
        print(f"Stack trace: {trace}")
        
        # Check if the error message contains information about file size limits
        error_msg = str(e).lower()
        if "413" in error_msg or "entity too large" in error_msg or "size limit" in error_msg or "exceeded" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Audio file is too large for the OpenAI API. Please use a shorter audio clip (under 25MB)."
            )
        elif "ffmpeg" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="There was an issue processing the audio file. The server will attempt to use a fallback method."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing request: {str(e)}"
            )

# --- Summarization & Timestamp Extraction Endpoint ---
class SummarizeRequest(BaseModel):
    transcript: str

@app.post("/api/summarize")
def summarize_transcript(request: SummarizeRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        # Show a loading message in the response
        print(f"Received transcript for summarization, length: {len(request.transcript)} chars")
        
        # Make a direct API call to the OpenAI Chat Completions API using GPT-4o
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o',
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant that summarizes podcast transcripts and extracts key timestamps.'
                },
                {
                    'role': 'user',
                    'content': f"Summarize the following podcast transcript and extract key timestamps for important segments:\n\n{request.transcript}"
                }
            ],
            'temperature': 0.5,
            'max_tokens': 1000
        }
        
        print("Calling OpenAI Chat Completions API with GPT-4o model")
        api_response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=120  # Increased timeout for longer processing
        )
        
        # Check for successful response
        if api_response.status_code == 200:
            result = api_response.json()
            if 'choices' in result and len(result['choices']) > 0:
                summary = result['choices'][0]['message']['content'].strip()
                print(f"Successfully generated summary with GPT-4o, length: {len(summary)} chars")
                return {"summary": summary}
            else:
                error_msg = "No choices in response"
                print(f"API error: {error_msg}")
                raise HTTPException(status_code=500, detail=f"Summarization failed: {error_msg}")
        else:
            # Handle API errors
            error_detail = "Unknown error"
            try:
                error_json = api_response.json()
                if 'error' in error_json:
                    error_detail = error_json['error'].get('message', 'Unknown error')
            except:
                error_detail = api_response.text or f"HTTP error {api_response.status_code}"
            
            print(f"API error: {error_detail}")
            raise HTTPException(status_code=500, detail=f"OpenAI API error: {error_detail}")
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
    except Exception as e:
        trace = traceback.format_exc()
        print(f"Summarization failed: {str(e)}")
        print(f"Stack trace: {trace}")
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

# Run with: uvicorn main:app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 