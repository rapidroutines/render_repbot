class ExerciseCounter {
    constructor() {
        // Cache DOM elements
        this.video = document.getElementById('input-video');
        this.canvas = document.getElementById('output-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.repDisplay = document.getElementById('rep-counter');
        this.exerciseSelector = document.getElementById('exercise-type');
        this.startButton = document.getElementById('start-camera');
        this.feedbackDisplay = document.getElementById('feedback-display');
        this.exerciseContainer = document.getElementById('exercise-container');

        // Initialize state variables
        this.repCounter = 0;
        this.stage = "down";
        this.camera = null;
        
        // Generate a unique session ID for this user
        this.sessionId = 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        console.log("Session ID created:", this.sessionId);
        
        // Backend URL
        this.backendUrl = "https://render-chatbot1-a8hc.onrender.com";

        // Inactivity tracking
        this.lastActivityTime = Date.now();
        this.inactivityTimeout = 180000; // 3 minutes 
        this.inactivityTimer = null;
        this.lastLandmarks = null;
        this.noMovementFrames = 0;
        this.movementThreshold = 0.05; // Threshold for detecting movement
        this.maxNoMovementFrames = 150;
        
        // Key points for movement detection (optimization)
        this.keyPoints = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]; // Head, shoulders, arms, hips, legs

        // Dashboard URL - direct external link
        this.dashboardUrl = "https://render-repbot.vercel.app/";

        // Setup canvas size responsively
        this.resize_canvas();
        window.addEventListener('resize', this.resize_canvas.bind(this));

        // Initialize MediaPipe Pose
        this.initialize_pose();

        // Event listeners
        this.exerciseSelector.addEventListener('change', this.handle_exercise_change.bind(this));
        this.startButton.addEventListener('click', this.start_camera.bind(this));
        
        // Bind activity reset events
        const resetActivity = this.reset_inactivity_timer.bind(this);
        document.addEventListener('mousemove', resetActivity);
        document.addEventListener('keydown', resetActivity);
        document.addEventListener('click', resetActivity);
        document.addEventListener('touchstart', resetActivity);
    }

    handle_exercise_change() {
        console.log("Exercise changed to:", this.exerciseSelector.value);
        this.repCounter = 0;
        this.repDisplay.innerText = '0';
        this.stage = "down";
        
        if (this.feedbackDisplay) {
            this.feedbackDisplay.innerText = '';
        }
        
        this.reset_inactivity_timer();
    }

    resize_canvas() {
        const containerWidth = this.exerciseContainer.clientWidth;
        const containerHeight = this.exerciseContainer.clientHeight;

        this.canvas.width = containerWidth;
        this.canvas.height = containerHeight;
    }

    initialize_pose() {
        console.log('Initializing MediaPipe Pose...');
        this.pose = new Pose({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
        });

        this.pose.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });

        this.pose.onResults(this.on_results.bind(this));
        console.log('MediaPipe initialized successfully');
    }

    async start_camera() {
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

            // Wait for video to be ready
            await new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    this.video.play().then(resolve);
                };
            });

            // Setup the camera with MediaPipe
            this.camera = new Camera(this.video, {
                onFrame: async () => await this.pose.send({image: this.video}),
                width: 1280,
                height: 720
            });

            await this.camera.start();
            console.log("Camera started successfully");

            // Start inactivity timer
            this.start_inactivity_timer();

        } catch (error) {
            console.error('Error starting camera:', error);
            this.show_camera_error(error.message);
            this.startButton.style.display = 'block';
        }
    }

    show_camera_error(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'camera-error';
        errorElement.innerHTML = `
            <p>Camera Error: ${message}</p>
            <p>Please ensure you've granted camera permissions and try again.</p>
        `;
        this.exerciseContainer.appendChild(errorElement);

        // Remove error message after 5 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 5000);
    }

    on_results(results) {
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
            this.detect_movement(results.poseLandmarks);

            // Send landmarks to backend for processing
            this.send_landmarks_to_backend(results.poseLandmarks);
        }
    }

    detect_movement(landmarks) {
        // If no previous landmarks, store current ones and return
        if (!this.lastLandmarks) {
            this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
            return;
        }

        // Check if there's significant movement between frames
        let movement = false;
        
        // Check key landmarks for movement
        for (const i of this.keyPoints) {
            if (landmarks[i] && this.lastLandmarks[i]) {
                const dx = landmarks[i].x - this.lastLandmarks[i].x;
                const dy = landmarks[i].y - this.lastLandmarks[i].y;
                // Using square of distance to avoid expensive square root operation
                const distanceSquared = dx*dx + dy*dy;
                
                if (distanceSquared > this.movementThreshold * this.movementThreshold) {
                    movement = true;
                    break;
                }
            }
        }

        // Update movement counter
        if (movement) {
            this.noMovementFrames = 0;
            this.reset_inactivity_timer(); // Reset inactivity timer on movement
        } else {
            this.noMovementFrames++;
            
            // If no movement for maxNoMovementFrames consecutive frames, consider inactive
            if (this.noMovementFrames >= this.maxNoMovementFrames) {
                this.check_inactivity();
            }
        }

        // Store current landmarks for next comparison
        this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
    }

    async send_landmarks_to_backend(landmarks) {
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
                this.reset_inactivity_timer();
            }
            
            this.update_ui_from_response(result);
        } catch (error) {
            console.error('Error sending landmarks to backend:', error);
            // Handle error appropriately
            if (this.feedbackDisplay) {
                this.feedbackDisplay.innerText = `Connection error: ${error.message}`;
            }
        }
    }

    update_ui_from_response(result) {
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
            this.display_angles(result.angles);
        }
    }

    display_angles(angles) {
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
    start_inactivity_timer() {
        this.reset_inactivity_timer();
        console.log("Inactivity timer started");
    }

    reset_inactivity_timer() {
        // Clear existing timer
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
        }
        
        // Update last activity time
        this.lastActivityTime = Date.now();
        
        // Set new timer
        this.inactivityTimer = setTimeout(() => {
            this.check_inactivity();
        }, this.inactivityTimeout);
    }

    check_inactivity() {
        const inactiveTime = Date.now() - this.lastActivityTime;
        
        // If inactive for longer than timeout, redirect
        if (inactiveTime >= this.inactivityTimeout) {
            console.log("User inactive, redirecting to dashboard...");
            this.show_redirect_notice();
        }
    }

    show_redirect_notice() {
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
            this.reset_inactivity_timer();
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
                // Redirect to external URL
                window.location.href = this.dashboardUrl;
            }
        }, 1000);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log("Initializing Exercise Counter...");
    new ExerciseCounter();
});
