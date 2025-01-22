document.addEventListener('DOMContentLoaded', function() {
    const chatbotButton = document.querySelector('.chatbot-button');
    const chatWindow = document.querySelector('.chat-window');
    const chatMessages = document.querySelector('.chat-messages');
    const messageForm = document.querySelector('.chat-form');
    const messageInput = document.querySelector('.chat-form input');
    const micButton = document.querySelector('.mic-button');
    const audioPermissionModal = new bootstrap.Modal(document.getElementById('audioPermissionModal'));
    let isOpen = false;
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    if (!chatbotButton || !chatWindow) return;

    // Initialize audio context for visualization
    let audioContext;
    let analyser;
    let microphone;

    // Add close button to chat header
    const chatHeader = document.querySelector('.chat-header');
    if (chatHeader) {
        chatHeader.innerHTML = `
            <h5>Medical Assistant</h5>
            <button class="chat-close-btn">&times;</button>
        `;
    }

    // Add typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = `
        <span></span>
        <span></span>
        <span></span>
    `;
    chatMessages.appendChild(typingIndicator);

    function showTypingIndicator() {
        typingIndicator.classList.add('active');
    }

    function hideTypingIndicator() {
        typingIndicator.classList.remove('active');
    }

    // Audio permission handling
    async function requestAudioPermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setupAudioRecording(stream);
            audioPermissionModal.hide();
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Unable to access microphone. Please check your browser settings.');
        }
    }

    // Setup audio recording with the provided stream
    function setupAudioRecording(stream) {
        mediaRecorder = new MediaRecorder(stream);

        // Set up audio context for visualization
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        microphone = audioContext.createMediaStreamSource(stream);
        microphone.connect(analyser);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio', audioBlob);

            try {
                showTypingIndicator();
                const response = await fetch('/api/chat/voice', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Failed to process voice message');
                }

                const data = await response.json();
                hideTypingIndicator();

                // Handle the response similar to text messages
                if (data.message) {
                    addMessage(data.message, false, data.options);
                    // Play the synthesized response if available
                    if (data.audio_response) {
                        playAudioResponse(data.audio_response);
                    }
                }

            } catch (error) {
                console.error('Error:', error);
                hideTypingIndicator();
                addMessage('Sorry, I had trouble processing your voice message. Please try again.', false);
            }

            audioChunks = [];
        };
    }

    // Add a message to the chat
    function addMessage(content, isUser = false, options = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

        // Handle regular text messages
        if (typeof content === 'string') {
            messageDiv.textContent = content;
        } else {
            messageDiv.innerHTML = content;
        }

        chatMessages.appendChild(messageDiv);

        // Add options if provided
        if (options && options.length > 0) {
            const optionsDiv = document.createElement('div');
            optionsDiv.className = 'message-options';

            options.forEach(option => {
                const button = document.createElement('button');
                button.className = 'option-button';
                button.textContent = option;
                button.onclick = () => sendMessage(option);
                optionsDiv.appendChild(button);
            });

            chatMessages.appendChild(optionsDiv);
        }

        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendMessage(message) {
        // Add user message to chat
        addMessage(message, true);

        // Show typing indicator
        showTypingIndicator();

        try {
            const response = await fetch('/api/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error('Failed to send message');
            }

            const data = await response.json();

            // Hide typing indicator
            hideTypingIndicator();

            // Handle different response types
            if (data.message) {
                addMessage(data.message, false, data.options);
                // Play audio response if available
                if (data.audio_response) {
                    playAudioResponse(data.audio_response);
                }
            }

            // Handle password input
            if (data.password) {
                messageInput.type = 'password';
            } else {
                messageInput.type = 'text';
            }

            // Handle successful login
            if (data.login_success) {
                window.location.reload();
            }

            // Update input state
            messageInput.disabled = !data.expect_input;
            if (!data.expect_input && messageForm) {
                messageForm.style.display = 'none';
            } else if (messageForm) {
                messageForm.style.display = 'flex';
            }

        } catch (error) {
            console.error('Error:', error);
            hideTypingIndicator();
            addMessage('Sorry, something went wrong. Please try again.', false);
        }
    }

    // Play audio response from the server
    async function playAudioResponse(audioData) {
        try {
            const audio = new Audio(`data:audio/wav;base64,${audioData}`);
            await audio.play();
        } catch (error) {
            console.error('Error playing audio response:', error);
        }
    }

    // Microphone button click handler
    if (micButton) {
        micButton.addEventListener('click', function() {
            if (!mediaRecorder) {
                audioPermissionModal.show();
                return;
            }

            if (!isRecording) {
                // Start recording
                audioChunks = [];
                mediaRecorder.start();
                isRecording = true;
                micButton.classList.add('recording');
            } else {
                // Stop recording
                mediaRecorder.stop();
                isRecording = false;
                micButton.classList.remove('recording');
            }
        });
    }

    // Audio permission request button handler
    const requestAudioPermissionButton = document.getElementById('requestAudioPermission');
    if (requestAudioPermissionButton) {
        requestAudioPermissionButton.addEventListener('click', requestAudioPermission);
    }

    // Toggle chat window
    chatbotButton.addEventListener('click', function() {
        isOpen = !isOpen;
        if (isOpen) {
            chatWindow.style.display = 'flex';
            setTimeout(() => {
                chatWindow.classList.add('active');
                // Send initial message to get help options
                sendMessage('help');
            }, 10);
        } else {
            chatWindow.classList.remove('active');
            setTimeout(() => {
                chatWindow.style.display = 'none';
            }, 300);
        }
    });

    // Close button functionality
    const closeButton = document.querySelector('.chat-close-btn');
    if (closeButton) {
        closeButton.addEventListener('click', function(e) {
            e.preventDefault();
            isOpen = false;
            chatWindow.classList.remove('active');
            setTimeout(() => {
                chatWindow.style.display = 'none';
            }, 300);
        });
    }

    // Handle message form submission
    if (messageForm) {
        messageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const message = messageInput.value.trim();
            if (message) {
                sendMessage(message);
                messageInput.value = '';
            }
        });
    }

    // Handle Enter key in input
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const message = this.value.trim();
                if (message) {
                    sendMessage(message);
                    this.value = '';
                }
            }
        });
    }
});