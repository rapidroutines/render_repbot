class ExerciseCounter {
    constructor() {
        this.video = document.getElementById('input-video');
        this.canvas = document.getElementById('output-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.repDisplay = document.getElementById('rep-counter');
        this.exerciseSelector = document.getElementById('exercise-type');
        this.startButton = document.getElementById('start-camera');
        this.feedbackDisplay = document.getElementById('feedback-display');
        this.containerElement = document.getElementById('exercise-container');

        this.repCounter = 0;
        this.stage = "down";
        this.camera = null;
        this.cameraActive = false;
        
        // Generate a unique session ID for this user
        this.sessionId = this.generateSessionId();
        console.log("Session ID created:", this.sessionId);
        
        // Backend URL - replace with your actual Render URL
        this.backendUrl = "https://render-chatbot1-a8hc.onrender.com";

        // Setup canvas size responsively
        this.resizeCanvas();
        window.addEventListener('resize', this.resizeCanvas.bind(this));

        // Listen for exercise changes
        this.exerciseSelector.addEventListener('change', () => {
            console.log("Exercise changed to:", this.exerciseSelector.value);
            this.repCounter = 0;
            this.repDisplay.innerText = '0';
            this.stage = "down";
            if (this.feedbackDisplay) {
                this.feedbackDisplay.innerText = '';
            }
        });

        // Start camera button event listener
        this.startButton.addEventListener('click', this.startCamera.bind(this));

        // Check if we're in an iframe
        this.isInIframe = window !== window.parent;
        console.log("Running in iframe:", this.isInIframe);

        // Automatically start camera if permissions were already granted
        this.checkCameraPermission().then(hasPermission => {
            if (hasPermission) {
                console.log("Camera permission already granted, starting camera automatically");
                // Small delay to ensure DOM is ready
                setTimeout(() => this.startCamera(), 500);
            }
        });

        // Handle messages from parent window if in iframe
        if (this.isInIframe) {
            window.addEventListener('message', this.handleParentMessage.bind(this));
            // Inform parent that we're ready
            this.sendMessageToParent({ type: 'ready' });
        }

        // Initialize MediaPipe Pose
        this.initializePose();
    }

    // Generate a random session ID for the user
    generateSessionId() {
        return 'user_' + Math.random().toString(36).substr(2, 9) + '_' + new Date().getTime();
    }

    // Send message to parent window if in iframe
    sendMessageToParent(message) {
        if (this.isInIframe) {
            window.parent.postMessage(message, '*');
        }
    }

    // Handle messages from parent window
    handleParentMessage(event) {
        const message = event.data;
        console.log("Message from parent:", message);

        if (message.type === 'startCamera') {
            this.startCamera();
        } else if (message.type === 'checkCameraPermission') {
            this.checkCameraPermission().then(hasPermission => {
                this.sendMessageToParent({ 
                    type: 'cameraPermissionStatus', 
                    hasPermission: hasPermission 
                });
            });
        }
    }

    // Check if camera permission is already granted
    async checkCameraPermission() {
        try {
            if (navigator.permissions && navigator.permissions.query) {
                const result = await navigator.permissions.query({ name: 'camera' });
                console.log("Camera permission status:", result.state);
                return result.state === 'granted';
            }
            
            // If permissions API is not supported, we'll have to try getting user media
            return false;
        } catch (error) {
            console.error("Error checking camera permission:", error);
            return false;
        }
    }

    resizeCanvas() {
        const container = document.getElementById('exercise-container');
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;

        this.canvas.width = containerWidth;
        this.canvas.height = containerHeight;
    }

    initializePose() {
        console.log('Initializing MediaPipe Pose...');
        this.pose = new Pose({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
            }
        });

        this.pose.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });

        this.pose.onResults(this.onResults.bind(this));
        console.log('MediaPipe initialized successfully');
    }

    async startCamera() {
        if (this.cameraActive) {
            console.log("Camera already active, ignoring request");
            return;
        }

        try {
            // Hide start button
            this.startButton.style.display = 'none';
            console.log("Starting camera...");

            // Check if getUserMedia is supported
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('getUserMedia is not supported in this browser');
            }

            // Show loading indicator
            this.showLoading();

            // Get user media constraints prioritizing the back camera on mobile
            const constraints = {
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };

            // Get user media stream
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = stream;

            // Return a promise that resolves when the video can play
            await new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    this.video.play().then(resolve);
                };
            });

            // Setup the camera with MediaPipe
            this.camera = new Camera(this.video, {
                onFrame: async () => {
                    await this.pose.send({image: this.video});
                },
                width: 1280,
                height: 720
            });

            await this.camera.start();
            this.cameraActive = true;
            this.hideLoading();
            console.log("Camera started successfully");

            // Notify parent window if in iframe
            this.sendMessageToParent({ type: 'cameraStarted', success: true });

        } catch (error) {
            console.error('Error starting camera:', error);
            this.showCameraError(error.message);
            this.startButton.style.display = 'block';
            this.hideLoading();

            // Notify parent window if in iframe
            this.sendMessageToParent({ 
                type: 'cameraStarted', 
                success: false, 
                error: error.message 
            });
        }
    }

    showLoading() {
        const loadingElement = document.createElement('div');
        loadingElement.className = 'camera-loading';
        loadingElement.innerHTML = `
            <div class="loading-spinner"></div>
            <p>Starting camera...</p>
        `;
        loadingElement.style.position = 'absolute';
        loadingElement.style.top = '0';
        loadingElement.style.left = '0';
        loadingElement.style.width = '100%';
        loadingElement.style.height = '100%';
        loadingElement.style.display = 'flex';
        loadingElement.style.flexDirection = 'column';
        loadingElement.style.alignItems = 'center';
        loadingElement.style.justifyContent = 'center';
        loadingElement.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        loadingElement.style.color = 'white';
        loadingElement.style.zIndex = '20';
        
        const spinner = loadingElement.querySelector('.loading-spinner');
        spinner.style.width = '40px';
        spinner.style.height = '40px';
        spinner.style.border = '4px solid rgba(255, 255, 255, 0.3)';
        spinner.style.borderTop = '4px solid #1e628c';
        spinner.style.borderRadius = '50%';
        spinner.style.animation = 'spin 1s linear infinite';
        
        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
        
        this.containerElement.appendChild(loadingElement);
        this.loadingElement = loadingElement;
    }

    hideLoading() {
        if (this.loadingElement && this.loadingElement.parentNode) {
            this.loadingElement.parentNode.removeChild(this.loadingElement);
            this.loadingElement = null;
        }
    }

    showCameraError(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'camera-error';
        errorElement.innerHTML = `
            <p>Camera Error: ${message}</p>
            <p>Please ensure you've granted camera permissions and try again.</p>
            <button id="retry-camera" class="retry-button">Try Again</button>
        `;
        document.getElementById('exercise-container').appendChild(errorElement);

        // Add event listener to retry button
        document.getElementById('retry-camera').addEventListener('click', () => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
            this.startCamera();
        });
    }

    onResults(results) {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw pose landmarks
        if (results.poseLandmarks) {
            // Draw connections and landmarks
            drawConnectors(this.ctx, results.poseLandmarks, POSE_CONNECTIONS, {
                color: '#1E628C',
                lineWidth: 2
            });
            drawLandmarks(this.ctx, results.poseLandmarks, {
                color: '#FF0000',
                lineWidth: 1,
                radius: 3
            });

            // Send landmarks to backend for processing
            this.sendLandmarksToBackend(results.poseLandmarks);
        }
    }

    async sendLandmarksToBackend(landmarks) {
        try {
            // Prepare the data to send
            const data = {
                landmarks: landmarks,
                exerciseType: this.exerciseSelector.value,
                sessionId: this.sessionId
            };

            // Send the data to the backend
            const response = await fetch(`${this.backendUrl}/process_landmarks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                mode: 'cors'
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            // Process the response
            const result = await response.json();
            this.updateUIFromResponse(result);
        } catch (error) {
            console.error('Error sending landmarks to backend:', error);
            // Handle error appropriately - maybe display a message to the user
            if (this.feedbackDisplay) {
                this.feedbackDisplay.innerText = `Connection error: ${error.message}`;
            }
        }
    }

    updateUIFromResponse(result) {
        // Update rep counter if changed
        if (result.repCounter !== undefined && this.repCounter !== result.repCounter) {
            this.repCounter = result.repCounter;
            this.repDisplay.innerText = this.repCounter;
        }

        // Update stage if changed
        if (result.stage !== undefined) {
            this.stage = result.stage;
        }

        // Display feedback if available
        if (result.feedback && this.feedbackDisplay) {
            this.feedbackDisplay.innerText = result.feedback;
        }

        // Display angles or other visual feedback if provided
        if (result.angles) {
            this.displayAngles(result.angles);
        }
    }

    displayAngles(angles) {
        // Display angles directly on the body parts
        this.ctx.font = "bold 16px Arial";
        this.ctx.lineWidth = 3;
        
        // Loop through all the angles and display them at their respective positions
        for (const [key, data] of Object.entries(angles)) {
            if (data.position && data.value !== undefined) {
                // Convert normalized coordinates to canvas coordinates
                const x = data.position.x * this.canvas.width;
                const y = data.position.y * this.canvas.height;
                
                // Create background for better visibility
                const text = `${key}: ${Math.round(data.value)}°`;
                const textWidth = this.ctx.measureText(text).width;
                
                // Draw background rectangle
                this.ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
                this.ctx.fillRect(x - textWidth/2 - 5, y - 20, textWidth + 10, 25);
                
                // Draw text
                this.ctx.fillStyle = "white";
                this.ctx.textAlign = "center";
                this.ctx.textBaseline = "middle";
                this.ctx.fillText(text, x, y - 7);
            }
        }
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log("Initializing Exercise Counter...");
    new ExerciseCounter();
});
