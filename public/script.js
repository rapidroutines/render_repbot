class ExerciseCounter {
    constructor() {
        this.video = document.getElementById('input-video');
        this.canvas = document.getElementById('output-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.repDisplay = document.getElementById('rep-counter');
        this.exerciseSelector = document.getElementById('exercise-type');
        this.startButton = document.getElementById('start-camera');
        this.feedbackDisplay = document.getElementById('feedback-display');

        this.repCounter = 0;
        this.stage = "down";
        this.camera = null;
        
        // Generate a unique session ID for this user
        this.sessionId = this.generateSessionId();
        console.log("Session ID created:", this.sessionId);
        
        // Backend URL - replace with your actual Render URL
        this.backendUrl = "https://render-chatbot1-a8hc.onrender.com";

        // Setup canvas size responsively
        this.resizeCanvas();
        window.addEventListener('resize', this.resizeCanvas.bind(this));

        // Initialize MediaPipe Pose
        this.initializePose();

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
    }

    // Generate a random session ID for the user
    generateSessionId() {
        return 'user_' + Math.random().toString(36).substr(2, 9) + '_' + new Date().getTime();
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
        try {
            // Hide start button
            this.startButton.style.display = 'none';
            console.log("Starting camera...");

            // Check if getUserMedia is supported
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('getUserMedia is not supported in this browser');
            }

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
            console.log("Camera started successfully");

        } catch (error) {
            console.error('Error starting camera:', error);
            this.showCameraError(error.message);
            this.startButton.style.display = 'block';
        }
    }

    showCameraError(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'camera-error';
        errorElement.innerHTML = `
            <p>Camera Error: ${message}</p>
            <p>Please ensure you've granted camera permissions and try again.</p>
        `;
        document.getElementById('exercise-container').appendChild(errorElement);

        // Remove error message after 5 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 5000);
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
        // Display angles on the canvas if provided by the backend
        this.ctx.fillStyle = "white";
        this.ctx.font = "18px Arial";
        
        let y = 30;
        for (const [key, value] of Object.entries(angles)) {
            this.ctx.fillText(`${key}: ${Math.round(value)}°`, 10, y);
            y += 25;
        }
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log("Initializing Exercise Counter...");
    new ExerciseCounter();
});
