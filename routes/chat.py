python
from flask import Blueprint, request, jsonify, session
from flask_login import current_user
from chatbot.handler import ChatbotHandler
import soundfile as sf
import numpy as np
import os
from datetime import datetime
from openai import OpenAI
import base64
import tempfile

chat_bp = Blueprint('chat', __name__)
chatbot = ChatbotHandler()

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

@chat_bp.route('/api/chat/message', methods=['POST'])
def handle_message():
    """Handle incoming chat messages"""
    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        # Get chatbot response
        chatbot_response = chatbot.process_message(message, current_user)

        # Get GPT response for enhanced conversation
        gpt_response = get_gpt_response(message, chatbot_response['message'])

        # Generate audio response
        audio_response = generate_speech(gpt_response)

        # Combine responses
        response = {
            **chatbot_response,
            'message': gpt_response,
            'audio_response': audio_response
        }

        return jsonify(response)
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        return jsonify({'error': 'Failed to process message'}), 500

@chat_bp.route('/api/chat/voice', methods=['POST'])
def handle_voice():
    """Handle voice messages"""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    try:
        # Save the uploaded audio file temporarily
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            audio_file.save(temp_file.name)

            # Transcribe audio using OpenAI Whisper
            with open(temp_file.name, 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                )

            # Clean up temporary file
            os.unlink(temp_file.name)

            # Get chatbot and GPT responses
            chatbot_response = chatbot.process_message(transcript.text, current_user)
            gpt_response = get_gpt_response(transcript.text, chatbot_response['message'])

            # Generate audio response
            audio_response = generate_speech(gpt_response)

            # Combine responses
            response = {
                **chatbot_response,
                'transcription': transcript.text,
                'message': gpt_response,
                'audio_response': audio_response
            }

            return jsonify(response)

    except Exception as e:
        print(f"Error processing voice message: {str(e)}")
        return jsonify({'error': 'Failed to process voice message'}), 500

def get_gpt_response(user_message, chatbot_response):
    """Get enhanced response from GPT-3.5 Turbo"""
    try:
        system_prompt = """You are a helpful medical assistant chatbot. Your responses should be:
        1. Clear and concise
        2. Professional but friendly
        3. Focused on medical appointment management
        4. Informative without being overwhelming

        When responding to medical queries, always remind users to consult with their healthcare provider 
        for specific medical advice."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": chatbot_response},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=150
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error getting GPT response: {str(e)}")
        return chatbot_response

def generate_speech(text):
    """Generate speech from text using TTS"""
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )

        # Save the audio temporarily and read it as base64
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            response.stream_to_file(temp_file.name)

            with open(temp_file.name, 'rb') as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode('utf-8')

            os.unlink(temp_file.name)
            return audio_data

    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        return None