document.addEventListener('DOMContentLoaded', () => {
    // Existing element selections
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const inputModeSelect = document.getElementById('input-mode');
    const voiceGenderSelect = document.getElementById('voice-gender');
    const statusDiv = document.getElementById('status');
    const audioPlayer = document.getElementById('audio-player');
    const recordButton = document.getElementById('record-button');
    const introSection = document.getElementById('intro-section');
    const startChatButton = document.getElementById('start-chat-button');
    const inputArea = document.querySelector('.input-area');
    const clearChatButton = document.getElementById('clear-chat-button');
    const muteButton = document.getElementById('mute-button');
    const stateSelect = document.getElementById('state-select'); // Already selected

    let mediaRecorder;
    let audioChunks = [];
    let isMuted = localStorage.getItem('isMuted') === 'true'; // Mute state persistence

    // ****** START: STATE PERSISTENCE LOGIC ******

    // 1. Load saved state on page load
    function loadSelectedState() {
        const savedState = localStorage.getItem('selectedUserState');
        if (savedState && stateSelect) {
            // Check if the saved value exists as an option
            const optionExists = Array.from(stateSelect.options).some(option => option.value === savedState);
            if (optionExists) {
                stateSelect.value = savedState;
                console.log(`Loaded saved state: ${savedState}`);
            } else {
                console.warn(`Saved state "${savedState}" not found in dropdown options. Defaulting.`);
                localStorage.removeItem('selectedUserState'); // Remove invalid state
                stateSelect.value = 'Select State'; // Set to default
            }
        } else if (stateSelect) {
             // Ensure default is selected if nothing is saved
             stateSelect.value = 'Select State';
        }
    }

    // Call this function early after DOM is ready and stateSelect is available
    if (stateSelect) { // Ensure dropdown exists before trying to load/add listener
        loadSelectedState();

        // 2. Save state when dropdown value changes
        stateSelect.addEventListener('change', () => {
            const currentState = stateSelect.value;
            localStorage.setItem('selectedUserState', currentState);
            console.log(`Saved selected state: ${currentState}`);
            // Optional: You could trigger a backend update here if needed immediately,
            // but current setup updates state on each message send anyway.
        });
    } else {
        console.error("State select dropdown not found!");
    }

    // 3. Clear saved state is handled in the clearChatButton listener below

    // ****** END: STATE PERSISTENCE LOGIC ******


    // --- Mute State Management ---
    function updateMuteButtonVisuals() {
        // ... (keep existing mute logic)
        if (isMuted) {
            muteButton.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
            muteButton.classList.add('muted');
            muteButton.title = "Unmute Audio";
            audioPlayer.muted = true;
        } else {
            muteButton.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            muteButton.classList.remove('muted');
            muteButton.title = "Mute Audio";
            audioPlayer.muted = false;
        }
    }
    updateMuteButtonVisuals();
    muteButton.addEventListener('click', () => {
        isMuted = !isMuted;
        localStorage.setItem('isMuted', isMuted);
        updateMuteButtonVisuals();
        if (isMuted && !audioPlayer.paused) console.log("Audio muted while playing.");
        else if (!isMuted && !audioPlayer.paused) console.log("Audio unmuted while playing.");
    });
    // --- End Mute State Management ---


    // Check if intro has been seen
    const introSeen = localStorage.getItem('introSeen');

    // --- Load chat history from localStorage on page load ---
    function loadLocalHistory() {
        // ... (keep existing history loading logic)
        const storedHistory = localStorage.getItem('chatHistory');
        chatHistory.innerHTML = '';
        if (storedHistory) {
            try {
                const history = JSON.parse(storedHistory);
                history.forEach(message => {
                    addMessage(message.content, message.sender, false); // Don't re-save history while loading
                });
            } catch (e) {
                console.error("Error parsing local chat history:", e);
                localStorage.removeItem('chatHistory');
            }
        }
    }


    // --- Initial UI Setup ---
    if (introSeen) {
        introSection.style.display = 'none';
        chatHistory.style.display = 'block';
        inputArea.style.display = 'flex'; // Use flex for the new footer layout
        loadLocalHistory();
        // Clear button visibility is handled by the observer/check function
    } else {
        introSection.style.display = 'block';
        chatHistory.style.display = 'none';
        inputArea.style.display = 'none';
        // Clear button should be hidden initially, handled by check function
    }


    // --- Save chat history to localStorage ---
    function saveChatHistory() {
        // ... (keep existing history saving logic)
        let messages = Array.from(chatHistory.querySelectorAll('.message')).map(messageDiv => {
             return {
                 content: messageDiv.textContent,
                 sender: messageDiv.classList.contains('user-message') ? 'user' : 'assistant',
                 timestamp: Date.now()
             };
        });
        try {
            const maxLocalMessages = 50;
            if (messages.length > maxLocalMessages) {
                messages = messages.slice(messages.length - maxLocalMessages);
            }
            localStorage.setItem('chatHistory', JSON.stringify(messages));
        } catch (error) {
             if (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED') {
                console.warn('Local storage quota likely exceeded.');
                // Simple strategy: just log for now. Could implement trimming oldest.
             } else {
                console.error('Error saving chat history to local storage:', error);
             }
        }
    }

    // --- Start Chat Button ---
    startChatButton.addEventListener('click', () => {
        introSection.style.display = 'none';
        chatHistory.style.display = 'block';
        inputArea.style.display = 'flex'; // Ensure footer is flex
        // Clear button visibility checked by observer/JS below
        localStorage.setItem('introSeen', 'true');
        addMessage("Hey there! What's up?", 'assistant', false); // Add greeting, don't save it to history storage yet
        statusDiv.textContent = 'Ready';
        // Ensure controls are enabled
        sendButton.disabled = false;
        recordButton.disabled = false;
        userInput.disabled = false;
        // Trigger visibility check for clear button might be needed here if chat starts empty
        setTimeout(() => {
             const clearChatGroup = clearChatButton?.closest('.control-group');
             if (clearChatGroup) clearChatGroup.style.display = 'none'; // Hide initially after start
        }, 50);
    });


    // --- Add Message to UI ---
    function addMessage(text, sender, save = true) {
        // ... (keep existing add message logic)
        console.log(`Adding message: "${text}" from ${sender}`);
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'assistant-message');
        messageDiv.textContent = text;

        if (chatHistory) {
            chatHistory.appendChild(messageDiv);
            // Scroll slightly before the bottom for better visibility of new message
            // chatHistory.scrollTop = chatHistory.scrollHeight; // Simple scroll to bottom
             chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: 'smooth' });

            if (save) {
                saveChatHistory(); // Save history AFTER adding message
            }
        } else {
            console.error('Error: chatHistory element not found!');
        }
    }


    // --- UI Mode Switching ---
    // ... (keep existing mode switching logic)
     inputModeSelect.addEventListener('change', () => {
         toggleInputMode(inputModeSelect.value);
     });
     function toggleInputMode(mode) {
         if (mode === 'voice') {
             userInput.style.display = 'none';
             sendButton.style.display = 'none';
             recordButton.style.display = 'flex';
             statusDiv.textContent = 'Voice mode. Click mic to record.';
             console.log("Switched to Voice Mode");
             stopRecording(); // Stop if switching TO voice while recording
         } else { // text mode
             userInput.style.display = 'block';
             sendButton.style.display = 'flex';
             recordButton.style.display = 'none';
             statusDiv.textContent = 'Text mode. Type your message.';
             console.log("Switched to Text Mode");
             // stopRecording(); // Already called if switching FROM voice
         }
     }
     toggleInputMode(inputModeSelect.value); // Initial setup


    // --- Sending Text Messages ---
    async function sendTextMessage(event, messageOverride = null) {
        // ... (keep existing text sending logic - it already reads stateSelect.value)
         if (event) event.preventDefault();
         const text = messageOverride !== null ? messageOverride : userInput.value.trim();
         if (!text) return;

         const selectedState = stateSelect.value; // Reads current state

         if (messageOverride === null) {
             addMessage(text, 'user'); // Adds and saves history via saveChatHistory() call inside
             userInput.value = '';
         }

         statusDiv.textContent = 'Naru is thinking...';
         sendButton.disabled = true;
         userInput.disabled = true;
         recordButton.disabled = true;

         try {
             const response = await fetch('/chat', {
                 method: 'POST',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({
                     message: text,
                     input_mode: 'text',
                     voice_gender: voiceGenderSelect.value,
                     selected_state: selectedState === 'Select State' ? null : selectedState
                 }),
             });
             await handleResponse(response); // handleResponse calls addMessage for assistant, which saves history
         } catch (error) {
             console.error('Error sending message:', error);
             addMessage(`Network Error: ${error.message}.`, 'assistant'); // Adds and saves history
             statusDiv.textContent = 'Error';
         } finally {
              sendButton.disabled = false;
              userInput.disabled = false;
              recordButton.disabled = false;
         }
    }


    // --- Handle Server Response (Audio or JSON) ---
    async function handleResponse(response) {
        // ... (keep existing response handling logic)
         const responseTextHeader = response.headers.get('X-Response-Text');
         let displayText = responseTextHeader ? responseTextHeader : '';

         if (!response.ok) {
              statusDiv.textContent = `Error: ${response.status}`;
              let errorMsg = `Server error (${response.status})`;
              try {
                  const errorData = await response.json();
                  errorMsg = errorData.error || errorData.message || errorMsg;
              } catch (e) {
                  try { errorMsg = await response.text() || errorMsg; } catch (e2) {}
              }
               addMessage(errorMsg, 'assistant'); // Adds and saves history
               sendButton.disabled = false;
               userInput.disabled = false;
               recordButton.disabled = false;
               return;
         }

         const contentType = response.headers.get("content-type");

         if (contentType && contentType.includes("audio/mpeg")) {
             statusDiv.textContent = isMuted ? 'Audio muted' : 'Playing...';
             if (displayText) {
                 addMessage(displayText, 'assistant'); // Adds and saves history
             } else {
                 console.warn("Received audio but no X-Response-Text header found.");
                 addMessage("[Audio response received]", 'assistant'); // Adds and saves history
             }
             const audioBlob = await response.blob();
             playAudio(audioBlob);
         } else if (contentType && contentType.includes("application/json")) {
              statusDiv.textContent = 'Ready';
              try {
                  const data = await response.json();
                  displayText = data.response_text || displayText || data.message;
                  if (displayText) {
                       addMessage(displayText, 'assistant'); // Adds and saves history
                  } else {
                      addMessage(data.error || "Received unexpected JSON response.", 'assistant'); // Adds and saves history
                  }
              } catch(e) {
                   console.error("Error parsing JSON response:", e);
                   addMessage("[Error processing server JSON response]", 'assistant'); // Adds and saves history
                   statusDiv.textContent = 'Error';
              }
         } else {
              statusDiv.textContent = 'Ready';
              try {
                  const textResponse = await response.text();
                  displayText = textResponse || displayText;
                  if (displayText) {
                       addMessage(displayText, 'assistant'); // Adds and saves history
                  } else {
                      addMessage(`Received unexpected response type: ${contentType || 'Unknown'}`, 'assistant'); // Adds and saves history
                  }
              } catch(e) {
                   console.error("Error reading unexpected response:", e);
                   addMessage("[Error reading server response]", 'assistant'); // Adds and saves history
                   statusDiv.textContent = 'Error';
              }
         }
    }


    // --- Play Audio Function ---
    function playAudio(audioBlob) {
        // ... (keep existing audio playing logic)
         const audioUrl = URL.createObjectURL(audioBlob);
         audioPlayer.src = audioUrl;
         console.log(`Attempting to play audio. Player muted: ${audioPlayer.muted}`);
         const playPromise = audioPlayer.play();
         if (playPromise !== undefined) {
              playPromise.catch(error => {
                 console.error("Error attempting to play audio:", error);
                 if (error.name === 'NotAllowedError') {
                     statusDiv.textContent = 'Click page to enable audio.';
                     addMessage("[System: Browser blocked audio playback. Click page or unmute.]", 'assistant', false); // Don't save system message
                 } else {
                     if (statusDiv.textContent !== 'Audio muted') statusDiv.textContent = 'Error playing audio.';
                     addMessage(`[System: Couldn't play audio - ${error.name}]`, 'assistant', false); // Don't save system message
                 }
                 URL.revokeObjectURL(audioUrl);
              });
         }
         audioPlayer.onended = () => {
             console.log("Audio playback finished.");
             if (statusDiv.textContent !== 'Audio muted' && statusDiv.textContent !== 'Click page to enable audio.') {
                  statusDiv.textContent = 'Ready';
             }
             URL.revokeObjectURL(audioUrl);
         };
         audioPlayer.onerror = (e) => {
             console.error("Audio playback error event:", e);
              if (statusDiv.textContent !== 'Audio muted' && statusDiv.textContent !== 'Click page to enable audio.') {
                 statusDiv.textContent = 'Error playing audio.';
              }
              addMessage("[System: Error during audio playback]", 'assistant', false); // Don't save system message
              URL.revokeObjectURL(audioUrl);
         };
         if (audioPlayer.muted && statusDiv.textContent !== 'Click page to enable audio.') {
              statusDiv.textContent = 'Audio muted';
         }
    }
    // --- End Play Audio Function ---


    // Event listeners for text input
    // ... (keep existing text input listeners)
     sendButton.addEventListener('click', sendTextMessage);
     userInput.addEventListener('keypress', (event) => {
         if (event.key === 'Enter' && !event.shiftKey) {
             event.preventDefault();
             sendTextMessage(null);
         }
     });

    // --- Voice Recording ---
    // ... (keep existing voice recording logic - onstop already reads stateSelect.value)
     recordButton.addEventListener('click', () => {
         if (mediaRecorder && mediaRecorder.state === "recording") stopRecording();
         else startRecording();
     });
     async function startRecording() {
          if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
              addMessage("Media Devices API not supported.", "assistant"); statusDiv.textContent = "Error: Mic not supported"; return;
          }
          try {
              const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
              const options = { mimeType: 'audio/webm;codecs=opus' };
               if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                   console.warn(`${options.mimeType} not supported, trying audio/webm.`); options.mimeType = 'audio/webm';
                   if (!MediaRecorder.isTypeSupported(options.mimeType)) { console.warn(`${options.mimeType} not supported. Using browser default.`); delete options.mimeType; }
               }
              mediaRecorder = new MediaRecorder(stream, options);
              audioChunks = [];
              mediaRecorder.ondataavailable = event => { if (event.data.size > 0) audioChunks.push(event.data); };
              mediaRecorder.onstop = async () => {
                  recordButton.classList.remove('recording'); recordButton.innerHTML = '<i class="fa-solid fa-microphone"></i>';
                  recordButton.disabled = true; statusDiv.textContent = 'Processing voice...';
                  stream.getTracks().forEach(track => track.stop());
                  if (audioChunks.length === 0) { console.warn("No audio data recorded."); statusDiv.textContent = "No audio detected."; recordButton.disabled = false; return; }
                  const blobType = mediaRecorder.mimeType || 'audio/webm';
                  const audioBlob = new Blob(audioChunks, { type: blobType }); audioChunks = [];
                  const selectedState = stateSelect.value; // Reads current state
                  const formData = new FormData();
                  const filename = `recording_${Date.now()}.${blobType.split('/')[1].split(';')[0] || 'webm'}`;
                  formData.append('audio_data', audioBlob, filename);
                  formData.append('voice_gender', voiceGenderSelect.value);
                  formData.append('selected_state', selectedState === 'Select State' ? '' : selectedState); // Sends current state
                  try {
                      const response = await fetch('/voice_input', { method: 'POST', body: formData });
                      await handleResponse(response); // handleResponse adds message and saves history
                  } catch (error) {
                      console.error('Error sending voice input:', error);
                      addMessage(`Network Error sending voice: ${error.message}.`, 'assistant'); // Adds and saves history
                      statusDiv.textContent = 'Error';
                  } finally { recordButton.disabled = false; }
              }; // End of onstop
              mediaRecorder.onerror = (event) => {
                   console.error("MediaRecorder error:", event.error); statusDiv.textContent = "Recording error.";
                   addMessage(`[System: Recording failed: ${event.error.name || 'Unknown error'}]`, 'assistant'); // Adds and saves history
                   recordButton.classList.remove('recording'); recordButton.innerHTML = '<i class="fa-solid fa-microphone"></i>'; recordButton.disabled = false;
                   stream.getTracks().forEach(track => track.stop());
              };
              mediaRecorder.start();
              recordButton.classList.add('recording'); recordButton.innerHTML = '<i class="fa-solid fa-stop"></i>'; recordButton.disabled = false; statusDiv.textContent = 'Recording...';
          } catch (err) {
              console.error("Error accessing microphone:", err); statusDiv.textContent = 'Mic access error.';
              if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') { addMessage("Mic access denied.", 'assistant'); statusDiv.textContent = 'Mic permission denied.'; }
              else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') { addMessage("No microphone found.", 'assistant'); statusDiv.textContent = 'Mic not found.'; }
              else { addMessage(`Error accessing mic: ${err.name} - ${err.message}`, 'assistant'); }
              recordButton.classList.remove('recording'); recordButton.innerHTML = '<i class="fa-solid fa-microphone"></i>'; recordButton.disabled = false;
          }
     }
     function stopRecording() {
         if (mediaRecorder && mediaRecorder.state === "recording") {
             mediaRecorder.stop(); recordButton.disabled = true; statusDiv.textContent = 'Stopping...';
         }
     }


    // --- Clear Chat Functionality ---
    clearChatButton.addEventListener('click', async () => {
        const confirmClear = confirm("Are you sure you want to clear the chat history and reset settings?"); // Updated confirmation message
        if (!confirmClear) {
             return;
        }

        // Clear local storage items
        localStorage.removeItem('chatHistory');
        localStorage.removeItem('introSeen');
        // ****** ADDED: Clear saved state ******
        localStorage.removeItem('selectedUserState');
        // ****** END ADDED ******
        // Optional: Clear mute state too?
        // localStorage.removeItem('isMuted');
        // isMuted = false; // Reset variable
        // updateMuteButtonVisuals(); // Update UI

        chatHistory.innerHTML = ''; // Clear display

        // ****** ADDED: Reset dropdowns ******
        if(stateSelect) stateSelect.value = 'Select State'; // Reset state dropdown
        if(inputModeSelect) inputModeSelect.value = 'text'; // Reset mode
        if(voiceGenderSelect) voiceGenderSelect.value = 'female'; // Reset voice gender (or your default)
        toggleInputMode('text'); // Update UI for text mode
        // ****** END ADDED ******

        // Clear server-side history (optional, keep if needed)
        try {
            statusDiv.textContent = 'Clearing server history...';
            const response = await fetch('/clear_history', { method: 'POST' });
            if (!response.ok) {
                 let serverError = `Server error ${response.status}`;
                 try { serverError = (await response.json()).message || serverError } catch {}
                 console.error("Failed to clear server-side history:", serverError);
                  statusDiv.textContent = 'Error clearing server history.';
            } else {
                 const result = await response.json();
                 console.log("Server response for clear:", result.message);
                 statusDiv.textContent = 'History Cleared. Start a new chat!';
            }
        } catch (error) {
            console.error('Network error while clearing server-side history:', error);
             statusDiv.textContent = 'Network error clearing history.';
        }

        // Reset UI to initial state
        introSection.style.display = 'block';
        chatHistory.style.display = 'none';
        inputArea.style.display = 'none';
        // Clear button visibility handled by observer/check function

        // Close the dropdown if it's open
        const dropdownControls = document.getElementById('dropdown-controls');
        const dropdownToggleBtn = document.getElementById('dropdown-toggle-button');
        if (dropdownControls && dropdownControls.classList.contains('visible')) {
            dropdownControls.classList.remove('visible');
            if(dropdownToggleBtn) dropdownToggleBtn.setAttribute('title', 'Settings');
        }
    });


    // --- Initial setup ---
    // Visibility logic for clear button etc. is handled by the embedded script in HTML now
    // Make sure that script runs AFTER this main script or put its core logic here.
    // Example: Call checkClearButtonVisibility from HTML script here after defining it.

}); // End of DOMContentLoaded