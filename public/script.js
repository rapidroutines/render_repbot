class ExerciseCounter {
    constructor() {
        this.video = document.getElementById('input-video');
        this.canvas = document.getElementById('output-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.repDisplay = document.getElementById('rep-counter');
        this.exerciseSelector = document.getElementById('exercise-type');
        this.startButton = document.getElementById('start-camera');
        this.feedbackDisplay = document.getElementById('feedback-display');
        this.exerciseContainer = document.getElementById('exercise-container');

        this.repCounter = 0;
        this.stage = "down";
        this.camera = null;
        
        this.sessionId = 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        
        this.backendUrl = "https://render-repbot.onrender.com";

        this.lastActivityTime = Date.now();
        this.inactivityTimeout = 180000; 
        this.inactivityTimer = null;
        this.lastLandmarks = null;
        this.noMovementFrames = 0;
        this.movementThreshold = 0.05; 
        this.maxNoMovementFrames = 150;
        
        this.keyPoints = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]; 

        this.redirectUrl = "https://render-repbot.vercel.app/";

        this.resize_canvas();
        window.addEventListener('resize', this.resize_canvas.bind(this));

        this.initialize_pose();

        this.exerciseSelector.addEventListener('change', this.handle_exercise_change.bind(this));
        this.startButton.addEventListener('click', this.start_camera.bind(this));
        
        const resetActivity = this.reset_inactivity_timer.bind(this);
        document.addEventListener('mousemove', resetActivity);
        document.addEventListener('keydown', resetActivity);
        document.addEventListener('click', resetActivity);
        document.addEventListener('touchstart', resetActivity);
    }

    handle_exercise_change() {
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
    }

    async start_camera() {
        try {
            this.startButton.style.display = 'none';

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('getUserMedia is not supported in this browser');
            }

            const constraints = {
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = stream;

            await new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    this.video.play().then(resolve);
                };
            });

            this.camera = new Camera(this.video, {
                onFrame: async () => await this.pose.send({image: this.video}),
                width: 1280,
                height: 720
            });

            await this.camera.start();

            this.start_inactivity_timer();

        } catch (error) {
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

        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 5000);
    }

    on_results(results) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (results.poseLandmarks) {
            drawConnectors(this.ctx, results.poseLandmarks, POSE_CONNECTIONS, {
                color: '#1E628C',
                lineWidth: 2
            });
            drawLandmarks(this.ctx, results.poseLandmarks, {
                color: '#FF0000',
                lineWidth: 1,
                radius: 3
            });

            this.detect_movement(results.poseLandmarks);

            this.send_landmarks_to_backend(results.poseLandmarks);
        }
    }

    detect_movement(landmarks) {
        if (!this.lastLandmarks) {
            this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
            return;
        }

        let movement = false;
        
        for (const i of this.keyPoints) {
            if (landmarks[i] && this.lastLandmarks[i]) {
                const dx = landmarks[i].x - this.lastLandmarks[i].x;
                const dy = landmarks[i].y - this.lastLandmarks[i].y;
                const distanceSquared = dx*dx + dy*dy;
                
                if (distanceSquared > this.movementThreshold * this.movementThreshold) {
                    movement = true;
                    break;
                }
            }
        }

        if (movement) {
            this.noMovementFrames = 0;
            this.reset_inactivity_timer(); 
        } else {
            this.noMovementFrames++;
            
            if (this.noMovementFrames >= this.maxNoMovementFrames) {
                this.check_inactivity();
            }
        }

        this.lastLandmarks = JSON.parse(JSON.stringify(landmarks));
    }

    async send_landmarks_to_backend(landmarks) {
        try {
            const data = {
                landmarks: landmarks,
                exerciseType: this.exerciseSelector.value,
                sessionId: this.sessionId
            };

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

            const result = await response.json();
            
            if (result.repCounter !== undefined && this.repCounter !== result.repCounter) {
                this.reset_inactivity_timer();
            }
            
            this.update_ui_from_response(result);
        } catch (error) {
            if (this.feedbackDisplay) {
                this.feedbackDisplay.innerText = `Connection error: ${error.message}`;
            }
        }
    }

    update_ui_from_response(result) {
        if (result.repCounter !== undefined && this.repCounter !== result.repCounter) {
            this.repCounter = result.repCounter;
            this.repDisplay.innerText = this.repCounter;
        }

        if (result.stage !== undefined) {
            this.stage = result.stage;
        }

        if (result.feedback && this.feedbackDisplay) {
            this.feedbackDisplay.innerText = result.feedback;
        }

        if (result.angles) {
            this.display_angles(result.angles);
        }
    }

    display_angles(angles) {
        this.ctx.font = "bold 16px Arial";
        this.ctx.lineWidth = 3;
        
        for (const [key, data] of Object.entries(angles)) {
            if (data.position && data.value !== undefined) {
                const x = data.position.x * this.canvas.width;
                const y = data.position.y * this.canvas.height;
                
                const text = `${key}: ${Math.round(data.value)}°`;
                const textWidth = this.ctx.measureText(text).width;
                
                this.ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
                this.ctx.fillRect(x - textWidth/2 - 5, y - 20, textWidth + 10, 25);
                
                this.ctx.fillStyle = "white";
                this.ctx.textAlign = "center";
                this.ctx.textBaseline = "middle";
                this.ctx.fillText(text, x, y - 7);
            }
        }
    }

    start_inactivity_timer() {
        this.reset_inactivity_timer();
    }

    reset_inactivity_timer() {
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
        }
        
        this.lastActivityTime = Date.now();
        
        this.inactivityTimer = setTimeout(() => {
            this.check_inactivity();
        }, this.inactivityTimeout);
    }

    check_inactivity() {
        const inactiveTime = Date.now() - this.lastActivityTime;
        
        if (inactiveTime >= this.inactivityTimeout) {
            this.show_redirect_notice();
        }
    }

    show_redirect_notice() {
        const noticeElement = document.createElement('div');
        noticeElement.className = 'redirect-notice';
        noticeElement.innerHTML = `
            <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                        background: rgba(0, 0, 0, 0.7); z-index: 100; display: flex; 
                        flex-direction: column; justify-content: center; align-items: center; color: white;">
                <h2>No activity detected</h2>
                <p>Redirecting to RepBot Start Screen in <span id="countdown">5</span> seconds...</p>
                <button id="stay-button" style="padding: 10px 20px; margin-top: 20px; 
                                                background: #1e628c; border: none; color: white; 
                                                border-radius: 5px; cursor: pointer;">
                    Stay on this page
                </button>
            </div>
        `;
        
        document.body.appendChild(noticeElement);
        
        document.getElementById('stay-button').addEventListener('click', () => {
            if (noticeElement.parentNode) {
                noticeElement.parentNode.removeChild(noticeElement);
            }
            this.reset_inactivity_timer();
        });
        
        let secondsLeft = 5;
        const countdownElement = document.getElementById('countdown');
        
        const countdownInterval = setInterval(() => {
            secondsLeft--;
            if (countdownElement) {
                countdownElement.textContent = secondsLeft;
            }
            
            if (secondsLeft <= 0) {
                clearInterval(countdownInterval);
                window.location.href = this.redirectUrl;
            }
        }, 1000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ExerciseCounter();
});
