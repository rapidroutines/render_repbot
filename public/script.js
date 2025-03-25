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

        // Inactivity tracking
        this.lastActivityTime = Date.now();
        this.inactivityTimeout = 180000; // 3 minutes (180 seconds) of inactivity before redirect
        this.inactivityTimer = null;
        this.lastLandmarks = null;
        this.noMovementFrames = 0;
        this.movementThreshold = 0.01; // Threshold for detecting movement
        this.maxNoMovementFrames = 150; // About 5 seconds at 30fps

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
            this.resetInactivityTimer(); // Reset inactivity timer on exercise change
        });

        // Start camera button event listener
        this.startButton.addEventListener('click', this.startCamera.bind(this));

        // Add event listeners for user activity
        document.addEventListener('mousemove', this.resetInactivityTimer.bind(this));
        document.addEventListener('keydown', this.resetInactivityTimer.bind(this));
        document.addEventListener('click', this.resetInactivityTimer.bind(this));
        document.addEventListener('touchstart', this.resetInactivityTimer.bind(this));
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

            // Start inactivity timer
            this.startInactivityTimer();

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

            // Check for movement
            this.detectMovement(results.poseLandmarks);

            // Send landmarks to backend for processing
            this.sendLandmarksToBackend(results.poseLandmarks);
        }
    }

    detectMovement(landmarks) {
        // If no previous landmarks, store current ones and return
        if (!this.lastLandmarks) {
            this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
            return;
        }

        // Check if there's significant movement between frames
        let movement = false;
        
        // We'll check a subset of key landmarks for performance
        const keyPoints = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]; // Head, shoulders, arms, hips, legs
        
        for (const i of keyPoints) {
            if (landmarks[i] && this.lastLandmarks[i]) {
                const dx = landmarks[i].x - this.lastLandmarks[i].x;
                const dy = landmarks[i].y - this.lastLandmarks[i].y;
                const distance = Math.sqrt(dx*dx + dy*dy);
                
                if (distance > this.movementThreshold) {
                    movement = true;
                    break;
                }
            }
        }

        // Update movement counter
        if (movement) {
            this.noMovementFrames = 0;
            this.resetInactivityTimer(); // Reset inactivity timer on movement
        } else {
            this.noMovementFrames++;
            
            // If no movement for maxNoMovementFrames consecutive frames, consider inactive
            if (this.noMovementFrames >= this.maxNoMovementFrames) {
                this.checkInactivity();
            }
        }

        // Store current landmarks for next comparison
        this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
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
            
            // If exercise is being performed (rep count increases), reset inactivity
            if (result.repCounter !== undefined && this.repCounter !== result.repCounter) {
                this.resetInactivityTimer();
            }
            
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

    // Inactivity detection methods
    startInactivityTimer() {
        this.resetInactivityTimer();
        console.log("Inactivity timer started");
    }

    resetInactivityTimer() {
        // Clear existing timer
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
        }
        
        // Update last activity time
        this.lastActivityTime = Date.now();
        
        // Set new timer
        this.inactivityTimer = setTimeout(() => {
            this.checkInactivity();
        }, this.inactivityTimeout);
    }

    checkInactivity() {
        const currentTime = Date.now();
        const inactiveTime = currentTime - this.lastActivityTime;
        
        // If inactive for longer than timeout, redirect
        if (inactiveTime >= this.inactivityTimeout) {
            console.log("User inactive, redirecting to dashboard...");
            this.showRedirectNotice();
        }
    }

    showRedirectNotice() {
        // Create a notice that will display before redirecting
        const noticeElement = document.createElement('div');
        noticeElement.className = 'redirect-notice';
        noticeElement.innerHTML = `
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                        background: rgba(0, 0, 0, 0.7); z-index: 100; display: flex; 
                        flex-direction: column; justify-content: center; align-items: center; color: white;">
                <h2>No activity detected</h2>
                <p>Redirecting to dashboard in <span id="countdown">5</span> seconds...</p>
                <button id="stay-button" style="padding: 10px 20px; margin-top: 20px; 
                                                background: #1e628c; border: none; color: white; 
                                                border-radius: 5px; cursor: pointer;">
                    Stay on this page
                </button>
            </div>
        `;
        
        document.body.appendChild(noticeElement);
        
        // Add event listener to the stay button
        document.getElementById('stay-button').addEventListener('click', () => {
            // Remove the notice and reset the timer
            if (noticeElement.parentNode) {
                noticeElement.parentNode.removeChild(noticeElement);
            }
            this.resetInactivityTimer();
        });
        
        // Start the countdown
        let secondsLeft = 5;
        const countdownElement = document.getElementById('countdown');
        
        const countdownInterval = setInterval(() => {
            secondsLeft--;
            if (countdownElement) {
                countdownElement.textContent = secondsLeft;
            }
            
            if (secondsLeft <= 0) {
                clearInterval(countdownInterval);
                window.location.href = "https://rapidroutines.org/dashboard/";
            }
        }, 1000);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log("Initializing Exercise Counter...");
    new ExerciseCounter();
});
