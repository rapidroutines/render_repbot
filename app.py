from flask import Flask, request, jsonify
from flask_cors import CORS
import math
import time
import os

# Create Flask app
app = Flask(__name__)

# Configure CORS with more permissive settings
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Allow all origins
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global state storage (could be replaced with a database in production)
exercise_states = {}

@app.route('/')
def index():
    """Simple route for the root URL to verify the API is running"""
    return jsonify({
        'status': 'online',
        'message': 'Exercise Counter API is running',
        'endpoints': {
            '/process_landmarks': 'POST - Process exercise landmarks from MediaPipe'
        }
    })

@app.route('/process_landmarks', methods=['POST'])
def process_landmarks():
    """Process landmarks from the frontend and return exercise data"""
    try:
        data = request.json
        landmarks = data.get('landmarks', [])
        exercise_type = data.get('exerciseType', 'bicepCurl')
        session_id = data.get('sessionId', request.remote_addr)  # Use provided session ID or fallback to IP
        
        # Generate a unique client key combining session ID and exercise type
        client_key = f"{session_id}_{exercise_type}"
        
        # Initialize state for this client if not exists or if exercise type changed
        if client_key not in exercise_states:
            exercise_states[client_key] = {
                'repCounter': 0,
                'stage': 'down',
                'lastRepTime': 0,
                'holdStart': 0,
                'leftArmStage': 'down',
                'rightArmStage': 'down',
                'leftArmHoldStart': 0,
                'rightArmHoldStart': 0,
                'exerciseType': exercise_type
            }
        
        client_state = exercise_states[client_key]
        current_time = int(time.time() * 1000)  # Current time in milliseconds
        rep_cooldown = 1000  # Prevent double counting
        hold_threshold = 500  # Time to hold at position
        
        # Process landmarks based on exercise type
        result = {
            'repCounter': client_state['repCounter'],
            'stage': client_state['stage'],
            'feedback': ''
        }
        
        # Process different exercise types
        if exercise_type == 'bicepCurl':
            result = process_bicep_curl(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'squat':
            result = process_squat(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'pushup':
            result = process_pushup(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'shoulderPress':
            result = process_shoulder_press(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'handstand':
            result = process_handstand(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'pullUp':
            result = process_pull_up(landmarks, client_state, current_time, rep_cooldown)
        elif exercise_type == 'situp':
            result = process_situp(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'jumpingJacks':
            result = process_jumping_jacks(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'lunge':
            result = process_lunge(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        
        # Update client state with the new values
        exercise_states[client_key] = client_state
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error processing landmarks: {str(e)}")
        return jsonify({'error': str(e)}), 500


def calculate_angle(a, b, c):
    """Calculate angle between three points"""
    try:
        # Convert to vector from pointB to pointA and pointB to pointC
        vector_ba = {
            'x': a['x'] - b['x'],
            'y': a['y'] - b['y']
        }

        vector_bc = {
            'x': c['x'] - b['x'],
            'y': c['y'] - b['y']
        }

        # Calculate dot product
        dot_product = vector_ba['x'] * vector_bc['x'] + vector_ba['y'] * vector_bc['y']

        # Calculate magnitudes
        magnitude_ba = math.sqrt(vector_ba['x']**2 + vector_ba['y']**2)
        magnitude_bc = math.sqrt(vector_bc['x']**2 + vector_bc['y']**2)

        # Calculate angle in radians (handle division by zero or invalid inputs)
        if magnitude_ba == 0 or magnitude_bc == 0:
            return 0
            
        cos_angle = dot_product / (magnitude_ba * magnitude_bc)
        
        # Handle floating point errors that could make cos_angle outside [-1, 1]
        cos_angle = max(min(cos_angle, 1.0), -1.0)
        
        angle_rad = math.acos(cos_angle)

        # Convert to degrees
        angle_deg = angle_rad * (180 / math.pi)
        
        return angle_deg
    
    except Exception as e:
        print(f"Error calculating angle: {str(e)}")
        return 0


def process_bicep_curl(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for bicep curl exercise"""
    try:
        # Left arm
        left_shoulder = landmarks[11]
        left_elbow = landmarks[13]
        left_wrist = landmarks[15]

        # Right arm
        right_shoulder = landmarks[12]
        right_elbow = landmarks[14]
        right_wrist = landmarks[16]

        # Track state for both arms
        left_angle = None
        right_angle = None
        left_curl_detected = False
        right_curl_detected = False
        angles = {}

        # Calculate and store left arm angle
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
            # Store angle with position data
            angles['L'] = {
                'value': left_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            }

            # Detect left arm curl
            if left_angle > 150:
                state['leftArmStage'] = "down"
                state['leftArmHoldStart'] = current_time
            if left_angle < 40 and state['leftArmStage'] == "down":
                if current_time - state['leftArmHoldStart'] > hold_threshold:
                    left_curl_detected = True
                    state['leftArmStage'] = "up"

        # Calculate and store right arm angle
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
            # Store angle with position data
            angles['R'] = {
                'value': right_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            }

            # Detect right arm curl
            if right_angle > 150:
                state['rightArmStage'] = "down"
                state['rightArmHoldStart'] = current_time
            if right_angle < 40 and state['rightArmStage'] == "down":
                if current_time - state['rightArmHoldStart'] > hold_threshold:
                    right_curl_detected = True
                    state['rightArmStage'] = "up"

        # Count rep if either arm completes a curl and enough time has passed since last rep
        if (left_curl_detected or right_curl_detected) and current_time - state['lastRepTime'] > rep_cooldown:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time
            
            # Generate feedback
            feedback = "Good rep!"
            if left_curl_detected and right_curl_detected:
                feedback = "Great form! Both arms curled."
            elif left_curl_detected:
                feedback = "Left arm curl detected."
            elif right_curl_detected:
                feedback = "Right arm curl detected."

            return {
                'repCounter': state['repCounter'],
                'stage': 'up' if left_curl_detected or right_curl_detected else 'down',
                'feedback': feedback,
                'angles': angles
            }

        return {
            'repCounter': state['repCounter'],
            'stage': state['leftArmStage'] if left_curl_detected else state['rightArmStage'],
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in bicep curl detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_squat(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for squat exercise with improved detection accuracy"""
    try:
        # Get landmarks for both legs
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        left_ankle = landmarks[27]
        right_hip = landmarks[24]
        right_knee = landmarks[26]
        right_ankle = landmarks[28]
        
        # Get additional landmarks for better squat detection
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]

        # Variables to store angles and status
        left_knee_angle = None
        right_knee_angle = None
        avg_knee_angle = None
        hip_shoulder_distance = None
        hip_ankle_distance = None
        angles = {}
        
        # Get initial hip height on first detection if not already set
        if 'initial_hip_height' not in state:
            if all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']):
                state['initial_hip_height'] = (left_hip['y'] + right_hip['y']) / 2
                print(f"Initial hip height set to: {state['initial_hip_height']}")
        
        # Calculate relative hip height to initial position (for squatting depth)
        relative_hip_height = None
        if 'initial_hip_height' in state:
            if all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']):
                current_hip_height = (left_hip['y'] + right_hip['y']) / 2
                relative_hip_height = (current_hip_height - state['initial_hip_height']) / state['initial_hip_height']
                # Store as a percentage increase (positive value means hips are lower than starting position)
                hip_height_pct = relative_hip_height * 100
                
                mid_x = (left_hip['x'] + right_hip['x']) / 2
                angles['HipDrop'] = {
                    'value': hip_height_pct,
                    'position': {
                        'x': mid_x,
                        'y': current_hip_height
                    }
                }

        # Calculate distance between shoulders and hips (for upper body angle)
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']) and \
           all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']):
            shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
            hip_mid_y = (left_hip['y'] + right_hip['y']) / 2
            hip_shoulder_distance = abs(hip_mid_y - shoulder_mid_y)
            
            # Store for debugging
            shoulder_mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
            angles['TorsoLen'] = {
                'value': hip_shoulder_distance * 100,
                'position': {
                    'x': shoulder_mid_x,
                    'y': (shoulder_mid_y + hip_mid_y) / 2
                }
            }

        # Calculate left knee angle if landmarks are visible
        if all(k in left_hip for k in ['x', 'y']) and all(k in left_knee for k in ['x', 'y']) and all(k in left_ankle for k in ['x', 'y']):
            left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            angles['L'] = {
                'value': left_knee_angle,
                'position': {
                    'x': left_knee['x'],
                    'y': left_knee['y']
                }
            }

        # Calculate right knee angle if landmarks are visible
        if all(k in right_hip for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y']):
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
            angles['R'] = {
                'value': right_knee_angle,
                'position': {
                    'x': right_knee['x'],
                    'y': right_knee['y']
                }
            }

        # Calculate average knee angle if both are available
        if left_knee_angle is not None and right_knee_angle is not None:
            avg_knee_angle = (left_knee_angle + right_knee_angle) / 2
            # Position between both knees
            mid_x = (left_knee['x'] + right_knee['x']) / 2
            mid_y = (left_knee['y'] + right_knee['y']) / 2
            angles['Avg'] = {
                'value': avg_knee_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y
                }
            }
        elif left_knee_angle is not None:
            avg_knee_angle = left_knee_angle
        elif right_knee_angle is not None:
            avg_knee_angle = right_knee_angle

        # Calculate hip to ankle distance (for squat width check)
        if all(k in left_hip for k in ['x', 'y']) and all(k in left_ankle for k in ['x', 'y']) and \
           all(k in right_hip for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y']):
            hip_mid_x = (left_hip['x'] + right_hip['x']) / 2
            ankle_mid_x = (left_ankle['x'] + right_ankle['x']) / 2
            hip_ankle_distance = abs(hip_mid_x - ankle_mid_x)
            
            # Store for debugging
            ankle_mid_y = (left_ankle['y'] + right_ankle['y']) / 2
            angles['StanceWidth'] = {
                'value': hip_ankle_distance * 100,
                'position': {
                    'x': (hip_mid_x + ankle_mid_x) / 2,
                    'y': (ankle_mid_y + ankle_mid_y) / 2
                }
            }

        # Process squat detection using knee angles and relative hip height
        feedback = ""
        
        # IMPROVED DETECTION LOGIC
        # We now use both knee angle and relative hip position for more accurate detection
        # This helps with different camera angles and body proportions
        
        # Standing position detection (straight legs)
        if avg_knee_angle is not None and avg_knee_angle > 150:
            if state['stage'] != "up":
                state['stage'] = "up"
                state['holdStart'] = current_time
                feedback = "Standing position - ready to squat"
        
        # Squat position detection (bent knees)
        # We use a more lenient knee angle threshold (130 degrees) and check relative hip drop
        if avg_knee_angle is not None and avg_knee_angle < 130:
            # If we have relative hip height measurement, use it as an additional check
            squat_depth_confirmed = False
            
            if relative_hip_height is not None:
                # A positive value means hips are lower than starting position
                if relative_hip_height > 0.1:  # Hip dropped at least 10% from starting position
                    squat_depth_confirmed = True
                    feedback = "Good squat depth!"
            else:
                # Fall back to just knee angle if we don't have relative hip height
                squat_depth_confirmed = True
            
            if squat_depth_confirmed and state['stage'] == "up":
                if current_time - state['holdStart'] > hold_threshold:
                    if current_time - state['lastRepTime'] > rep_cooldown:
                        state['stage'] = "down"
                        state['repCounter'] += 1
                        state['lastRepTime'] = current_time
                        feedback = "Rep complete! Great squat."
                else:
                    feedback = "Hold squat position"
            elif squat_depth_confirmed and state['stage'] == "down":
                feedback = "Return to standing position"
        
        # Form feedback for better squats
        if avg_knee_angle is not None:
            if state['stage'] == "up" and 130 < avg_knee_angle < 150:
                feedback = "Begin squat - bend knees more"
            elif state['stage'] == "down" and avg_knee_angle > 140:
                feedback = "Return to standing position fully"
        
        # More detailed form feedback if we have all the measurements
        if hip_ankle_distance is not None and hip_ankle_distance < 0.05:
            feedback = "Wider stance recommended for stability"
        
        # Debug information
        if 'initial_hip_height' in state:
            print(f"Current state: {state['stage']}, Knee angle: {avg_knee_angle}, " +
                  f"Hip relative: {relative_hip_height if relative_hip_height is not None else 'N/A'}")
        
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in squat detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }

def process_pushup(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for pushup exercise with improved detection accuracy"""
    try:
        # Get landmarks for both arms and shoulders
        left_shoulder = landmarks[11]
        left_elbow = landmarks[13]
        left_wrist = landmarks[15]
        right_shoulder = landmarks[12]
        right_elbow = landmarks[14]
        right_wrist = landmarks[16]

        # Additional body points for better pushup detection
        nose = landmarks[0]
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        left_knee = landmarks[25]
        right_knee = landmarks[26]
        left_ankle = landmarks[27]
        right_ankle = landmarks[28]

        # Variables to store angles and status
        left_elbow_angle = None
        right_elbow_angle = None
        avg_elbow_angle = None
        body_height = None
        body_alignment = None
        angles = {}
        
        # Save reference points if not already saved
        if 'reference_height' not in state:
            if all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']):
                # Average shoulder height in up position
                state['reference_height'] = (left_shoulder['y'] + right_shoulder['y']) / 2
                print(f"Reference height set to: {state['reference_height']}")
                
                # Also record typical distance between shoulders and hips for alignment checks
                if all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']):
                    shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
                    hip_mid_y = (left_hip['y'] + right_hip['y']) / 2
                    state['torso_length'] = abs(shoulder_mid_y - hip_mid_y)
                    print(f"Torso length set to: {state['torso_length']}")
        
        # Calculate left arm angle if landmarks are visible
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
            angles['L'] = {
                'value': left_elbow_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            }

        # Calculate right arm angle if landmarks are visible
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
            angles['R'] = {
                'value': right_elbow_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            }

        # Calculate average elbow angle if both are available
        if left_elbow_angle is not None and right_elbow_angle is not None:
            avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2
            mid_x = (left_elbow['x'] + right_elbow['x']) / 2
            mid_y = (left_elbow['y'] + right_elbow['y']) / 2
            angles['Avg'] = {
                'value': avg_elbow_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y
                }
            }
        elif left_elbow_angle is not None:
            avg_elbow_angle = left_elbow_angle
        elif right_elbow_angle is not None:
            avg_elbow_angle = right_elbow_angle

        # Calculate body alignment (straight back)
        # This is crucial for proper push-up form
        body_alignment_score = 0
        if (all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']) and 
            all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']) and
            all(k in left_ankle for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y'])):
            
            # Calculate midpoints
            shoulder_mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
            shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
            hip_mid_x = (left_hip['x'] + right_hip['x']) / 2
            hip_mid_y = (left_hip['y'] + right_hip['y']) / 2
            ankle_mid_x = (left_ankle['x'] + right_ankle['x']) / 2
            ankle_mid_y = (left_ankle['y'] + right_ankle['y']) / 2
            
            # Calculate alignment angles
            shoulder_hip_angle = calculate_angle(
                {'x': shoulder_mid_x, 'y': shoulder_mid_y - 0.1},  # point above shoulder
                {'x': shoulder_mid_x, 'y': shoulder_mid_y},  # shoulder
                {'x': hip_mid_x, 'y': hip_mid_y}  # hip
            )
            
            hip_ankle_angle = calculate_angle(
                {'x': shoulder_mid_x, 'y': hip_mid_y},  # hip
                {'x': hip_mid_x, 'y': hip_mid_y},  # hip
                {'x': ankle_mid_x, 'y': ankle_mid_y}  # ankle
            )
            
            # Calculate a 0-100 alignment score (100 = perfect alignment)
            # In a perfect push-up, both these angles should be close to 180 degrees
            alignment_score_1 = max(0, min(100, (shoulder_hip_angle / 180) * 100))
            alignment_score_2 = max(0, min(100, (hip_ankle_angle / 180) * 100))
            body_alignment_score = (alignment_score_1 + alignment_score_2) / 2
            
            # Store for visualization
            angles['Align'] = {
                'value': body_alignment_score,
                'position': {
                    'x': hip_mid_x,
                    'y': hip_mid_y
                }
            }
            
            # Special debug angle for troubleshooting
            angles['S-H-Angle'] = {
                'value': shoulder_hip_angle,
                'position': {
                    'x': (shoulder_mid_x + hip_mid_x) / 2,
                    'y': (shoulder_mid_y + hip_mid_y) / 2 - 0.05
                }
            }
            
            angles['H-A-Angle'] = {
                'value': hip_ankle_angle,
                'position': {
                    'x': (hip_mid_x + ankle_mid_x) / 2,
                    'y': (hip_mid_y + ankle_mid_y) / 2 - 0.05
                }
            }
        
        # Calculate relative shoulder height compared to reference
        rel_shoulder_height = None
        if 'reference_height' in state:
            if all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']):
                current_shoulder_height = (left_shoulder['y'] + right_shoulder['y']) / 2
                rel_shoulder_height = current_shoulder_height - state['reference_height']
                
                # A positive value means shoulders are lower than the reference position
                shoulder_height_pct = rel_shoulder_height * 100
                
                mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
                angles['ShoulderDrop'] = {
                    'value': shoulder_height_pct,
                    'position': {
                        'x': mid_x, 
                        'y': current_shoulder_height
                    }
                }
                
        # Check if we're in plank position (prerequisite for push-up)
        is_plank_position = False
        if body_alignment_score > 70:  # Requiring at least 70% alignment score
            # Also check if wrists are positioned correctly relative to shoulders
            if all(k in left_wrist for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
                wrist_mid_y = (left_wrist['y'] + right_wrist['y']) / 2
                shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
                
                # In a proper plank/push-up position, wrists should be at similar height as shoulders
                # or slightly below/above depending on the camera angle
                wrist_shoulder_y_diff = abs(wrist_mid_y - shoulder_mid_y)
                
                # Typical difference is less than 20% of the screen height in push-up position
                if wrist_shoulder_y_diff < 0.2:
                    is_plank_position = True
                    
                # Store for debugging
                angles['W-S-Diff'] = {
                    'value': wrist_shoulder_y_diff * 100,
                    'position': {
                        'x': (left_wrist['x'] + right_wrist['x']) / 2,
                        'y': (wrist_mid_y + shoulder_mid_y) / 2
                    }
                }

        # Process pushup detection using multiple factors
        feedback = ""
        
        # Only process pushups if we're in a plank-like position
        if is_plank_position and avg_elbow_angle is not None:
            # Up position detection (straight arms)
            if avg_elbow_angle > 150:
                if state['stage'] != "up":
                    state['stage'] = "up"
                    state['holdStart'] = current_time
                    feedback = "Up position - good plank!"
            
            # Down position detection (bent arms)
            if avg_elbow_angle < 110 and state['stage'] == "up":
                # Require a minimum time in the down position to count the rep
                if current_time - state['holdStart'] > hold_threshold:
                    if current_time - state['lastRepTime'] > rep_cooldown:
                        state['stage'] = "down"
                        state['repCounter'] += 1
                        state['lastRepTime'] = current_time
                        feedback = "Rep complete! Good push-up depth."
                    else:
                        feedback = "Down position - good form!"
                else:
                    feedback = "Down position - hold briefly"
        else:
            # If not in plank position but arms are being used
            if avg_elbow_angle is not None:
                if body_alignment_score < 70:
                    feedback = "Keep your body straight for proper push-ups"
                else:
                    feedback = "Get into push-up position with hands under shoulders"
            else:
                feedback = "Move to ensure arms are visible"
        
        # Debug info
        print(f"Stage: {state['stage']}, Elbow: {avg_elbow_angle}, Alignment: {body_alignment_score}, Plank: {is_plank_position}")

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in pushup detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_shoulder_press(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for shoulder press exercise"""
    try:
        # Get landmarks for both arms
        left_shoulder = landmarks[11]
        left_elbow = landmarks[13]
        left_wrist = landmarks[15]
        right_shoulder = landmarks[12]
        right_elbow = landmarks[14]
        right_wrist = landmarks[16]

        # Variables to store angles and positions
        left_elbow_angle = None
        right_elbow_angle = None
        left_wrist_above_shoulder = False
        right_wrist_above_shoulder = False
        angles = {}

        # Calculate left arm position and angle
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_elbow_angle = calculate_angle(left_wrist, left_elbow, left_shoulder)
            angles['L'] = {
                'value': left_elbow_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            }

            # Check if left wrist is above shoulder
            left_wrist_above_shoulder = left_wrist['y'] < left_shoulder['y']
            angles['LWristPos'] = {
                'value': 1 if left_wrist_above_shoulder else 0,
                'position': {
                    'x': left_wrist['x'],
                    'y': left_wrist['y']
                }
            }

        # Calculate right arm position and angle
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_elbow_angle = calculate_angle(right_wrist, right_elbow, right_shoulder)
            angles['R'] = {
                'value': right_elbow_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            }

            # Check if right wrist is above shoulder
            right_wrist_above_shoulder = right_wrist['y'] < right_shoulder['y']
            angles['RWristPos'] = {
                'value': 1 if right_wrist_above_shoulder else 0,
                'position': {
                    'x': right_wrist['x'],
                    'y': right_wrist['y']
                }
            }

        # Calculate average elbow angle if both are available
        avg_elbow_angle = None
        if left_elbow_angle is not None and right_elbow_angle is not None:
            avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2
            mid_x = (left_elbow['x'] + right_elbow['x']) / 2
            mid_y = (left_elbow['y'] + right_elbow['y']) / 2
            angles['Avg'] = {
                'value': avg_elbow_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y
                }
            }
        elif left_elbow_angle is not None:
            avg_elbow_angle = left_elbow_angle
        elif right_elbow_angle is not None:
            avg_elbow_angle = right_elbow_angle

        # Determine arm positions for stage detection
        both_wrists_below_shoulder = not left_wrist_above_shoulder and not right_wrist_above_shoulder
        both_wrists_above_shoulder = left_wrist_above_shoulder and right_wrist_above_shoulder
        one_wrist_above_shoulder = left_wrist_above_shoulder or right_wrist_above_shoulder

        # Process shoulder press detection
        feedback = ""
        if avg_elbow_angle is not None:
            # Starting (down) position - arms bent, wrists below shoulders
            if avg_elbow_angle < 100 and both_wrists_below_shoulder:
                state['stage'] = "down"
                state['holdStart'] = current_time
                feedback = "Ready position - good start"

            # Up position - arms extended, wrists above shoulders
            if avg_elbow_angle > 140 and (both_wrists_above_shoulder or (one_wrist_above_shoulder and avg_elbow_angle > 150)):
                if state['stage'] == "down" and current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "up"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    feedback = "Rep complete! Good press."
                elif state['stage'] == "up":
                    feedback = "Press complete - hold position"

            # Form feedback
            if state['stage'] == "down" and avg_elbow_angle < 65:
                feedback = "Start with arms higher"

            if one_wrist_above_shoulder and not both_wrists_above_shoulder and state['stage'] == "up":
                feedback = "Press both arms evenly"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in shoulder press detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_handstand(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for handstand exercise"""
    try:
        # Get key landmarks
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        left_knee = landmarks[25]
        right_knee = landmarks[26]
        left_ankle = landmarks[27]
        right_ankle = landmarks[28]

        # Check if all required landmarks are detected
        required_landmarks = [left_wrist, right_wrist, left_shoulder, right_shoulder, 
                            left_hip, right_hip, left_knee, right_knee, 
                            left_ankle, right_ankle]
        
        if not all(lm and all(k in lm for k in ['x', 'y']) for lm in required_landmarks):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Move to ensure full body is visible"
            }

        # Calculate angle between shoulder, hip, and knee (should be straight in a proper handstand)
        left_body_angle = calculate_angle(left_shoulder, left_hip, left_knee)
        right_body_angle = calculate_angle(right_shoulder, right_hip, right_knee)

        # Calculate angle between hip, knee, and ankle (should be straight in a proper handstand)
        left_leg_angle = calculate_angle(left_hip, left_knee, left_ankle)
        right_leg_angle = calculate_angle(right_hip, right_knee, right_ankle)

        # Check if wrists are below ankles (inverted position)
        avg_ankle_y = (left_ankle['y'] + right_ankle['y']) / 2
        avg_wrist_y = (left_wrist['y'] + right_wrist['y']) / 2
        is_inverted = avg_ankle_y < avg_wrist_y

        # Calculate distance between wrists (to check if hands are properly placed)
        wrist_distance = math.sqrt(
            (right_wrist['x'] - left_wrist['x'])**2 + 
            (right_wrist['y'] - left_wrist['y'])**2
        )

        # Calculate shoulder width for reference (to normalize wrist distance)
        shoulder_distance = math.sqrt(
            (right_shoulder['x'] - left_shoulder['x'])**2 + 
            (right_shoulder['y'] - left_shoulder['y'])**2
        )

        # Check if body is straight (angles close to 180 degrees)
        body_angle_threshold = 160  # Degrees, closer to 180 is straighter
        is_left_body_straight = abs(left_body_angle) > body_angle_threshold
        is_right_body_straight = abs(right_body_angle) > body_angle_threshold
        is_left_leg_straight = abs(left_leg_angle) > body_angle_threshold
        is_right_leg_straight = abs(right_leg_angle) > body_angle_threshold

        # Check if hands are properly placed (around shoulder width apart)
        wrist_distance_ratio = wrist_distance / shoulder_distance if shoulder_distance > 0 else 0
        is_hand_placement_good = 0.8 < wrist_distance_ratio < 1.5

        # Determine if handstand form is good
        is_good_form = (is_inverted and 
                       is_left_body_straight and is_right_body_straight and 
                       is_left_leg_straight and is_right_leg_straight and 
                       is_hand_placement_good)

        # Store angles for UI
        angles = {
            'LBody': {
                'value': left_body_angle,
                'position': {
                    'x': left_hip['x'],
                    'y': left_hip['y']
                }
            },
            'RBody': {
                'value': right_body_angle,
                'position': {
                    'x': right_hip['x'],
                    'y': right_hip['y']
                }
            },
            'LLeg': {
                'value': left_leg_angle,
                'position': {
                    'x': left_knee['x'],
                    'y': left_knee['y']
                }
            },
            'RLeg': {
                'value': right_leg_angle,
                'position': {
                    'x': right_knee['x'],
                    'y': right_knee['y']
                }
            },
            'WristRatio': {
                'value': wrist_distance_ratio,
                'position': {
                    'x': (left_wrist['x'] + right_wrist['x']) / 2,
                    'y': (left_wrist['y'] + right_wrist['y']) / 2
                }
            }
        }

        # Generate feedback based on form
        feedback = ""
        if not is_inverted:
            feedback = "Get into inverted position"
        elif not (is_left_body_straight and is_right_body_straight):
            feedback = "Keep your body straight"
        elif not (is_left_leg_straight and is_right_leg_straight):
            feedback = "Straighten your legs"
        elif not is_hand_placement_good:
            if wrist_distance_ratio < 0.8:
                feedback = "Place hands wider apart"
            else:
                feedback = "Place hands closer together"
        elif is_good_form:
            feedback = "Great handstand form!"

        # If in a good handstand position, track the hold time
        if is_good_form:
            if state['stage'] != "inverted":
                state['holdStart'] = current_time
                state['stage'] = "inverted"
                feedback = "Good handstand position - hold it!"

            # If held long enough, count as a rep
            if current_time - state['holdStart'] > hold_threshold and state['stage'] == "inverted":
                if current_time - state['lastRepTime'] > rep_cooldown:
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    feedback = "Handstand held! Great job!"
        else:
            # Reset if form breaks during a hold
            if state['stage'] == "inverted":
                state['stage'] = "normal"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in handstand detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_pull_up(landmarks, state, current_time, rep_cooldown):
    """Process landmarks for pull-up exercise"""
    try:
        # Get coordinates for both sides
        left_shoulder = landmarks[11]
        left_elbow = landmarks[13]
        left_wrist = landmarks[15]
        right_shoulder = landmarks[12]
        right_elbow = landmarks[14]
        right_wrist = landmarks[16]

        # Check if we have valid landmarks for at least one side
        left_valid = (left_shoulder and left_elbow and left_wrist and
                     all(k in left_shoulder for k in ['x', 'y']) and
                     all(k in left_elbow for k in ['x', 'y']) and
                     all(k in left_wrist for k in ['x', 'y']))
        
        right_valid = (right_shoulder and right_elbow and right_wrist and
                      all(k in right_shoulder for k in ['x', 'y']) and
                      all(k in right_elbow for k in ['x', 'y']) and
                      all(k in right_wrist for k in ['x', 'y']))

        if not left_valid and not right_valid:
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera"
            }

        # Calculate angles for both sides
        left_angle = None
        right_angle = None
        angles = {}

        if left_valid:
            left_angle = calculate_angle(
                {'x': left_shoulder['x'], 'y': left_shoulder['y']},
                {'x': left_elbow['x'], 'y': left_elbow['y']},
                {'x': left_wrist['x'], 'y': left_wrist['y']}
            )
            angles['L'] = {
                'value': left_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            }

        if right_valid:
            right_angle = calculate_angle(
                {'x': right_shoulder['x'], 'y': right_shoulder['y']},
                {'x': right_elbow['x'], 'y': right_elbow['y']},
                {'x': right_wrist['x'], 'y': right_wrist['y']}
            )
            angles['R'] = {
                'value': right_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            }

        # Average the angles if both sides are valid, otherwise use the valid one
        arm_angle = None
        if left_valid and right_valid:
            arm_angle = (left_angle + right_angle) / 2
            mid_x = (left_elbow['x'] + right_elbow['x']) / 2
            mid_y = (left_elbow['y'] + right_elbow['y']) / 2
            angles['Avg'] = {
                'value': arm_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y
                }
            }
        elif left_valid:
            arm_angle = left_angle
        else:
            arm_angle = right_angle

        # Store the previous stage to detect transitions
        previous_stage = state['stage']

        # Determine pull-up stage based on arm angle
        # For pull-ups, when arms are bent (small angle) we're in "up" position
        if arm_angle < 50:
            state['stage'] = "up"
        elif arm_angle > 150:
            state['stage'] = "down"

        # Generate feedback based on stage
        feedback = ""
        if state['stage'] == "up":
            feedback = "Up position - good!"
        elif state['stage'] == "down":
            feedback = "Down position - pull up!"

        # Count rep when transitioning from "up" to "down" with cooldown
        if previous_stage == "up" and state['stage'] == "down" and current_time - state['lastRepTime'] > rep_cooldown:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time
            feedback = "Rep complete! Good pull-up."

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in pull-up detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_situp(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for sit-up exercise"""
    try:
        # Get landmarks for both sides
        left_shoulder = landmarks[11]
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        right_shoulder = landmarks[12]
        right_hip = landmarks[24]
        right_knee = landmarks[26]

        # Initialize variables to track angles
        left_angle = 0
        right_angle = 0
        avg_angle = 0
        angles = {}

        # Check if we have all required landmarks
        if (left_shoulder and left_hip and left_knee and right_shoulder and right_hip and right_knee and
            all(k in left_shoulder for k in ['x', 'y']) and all(k in left_hip for k in ['x', 'y']) and 
            all(k in left_knee for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']) and 
            all(k in right_hip for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y'])):

            # Calculate angle for left side
            left_angle = calculate_angle(
                {'x': left_shoulder['x'], 'y': left_shoulder['y']},
                {'x': left_hip['x'], 'y': left_hip['y']},
                {'x': left_knee['x'], 'y': left_knee['y']}
            )
            angles['L'] = {
                'value': left_angle,
                'position': {
                    'x': left_hip['x'],
                    'y': left_hip['y']
                }
            }

            # Calculate angle for right side
            right_angle = calculate_angle(
                {'x': right_shoulder['x'], 'y': right_shoulder['y']},
                {'x': right_hip['x'], 'y': right_hip['y']},
                {'x': right_knee['x'], 'y': right_knee['y']}
            )
            angles['R'] = {
                'value': right_angle,
                'position': {
                    'x': right_hip['x'],
                    'y': right_hip['y']
                }
            }

            # Calculate average angle (for more stability)
            avg_angle = (left_angle + right_angle) / 2
            mid_x = (left_hip['x'] + right_hip['x']) / 2
            mid_y = (left_hip['y'] + right_hip['y']) / 2
            angles['Avg'] = {
                'value': avg_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y
                }
            }

            # Rep counting logic using average angle for more stability
            feedback = ""
            if avg_angle > 160:
                # Lying flat
                state['stage'] = "down"
                state['holdStart'] = current_time
                feedback = "Down position - prepare to sit up"

            if avg_angle < 80 and state['stage'] == "down":
                # Sitting up
                if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "up"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    feedback = "Rep complete! Good sit-up."
                else:
                    feedback = "Almost there - complete the sit-up"

            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': feedback,
                'angles': angles
            }
        else:
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera",
                'angles': {}
            }
        
    except Exception as e:
        print(f"Error in sit-up detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_jumping_jacks(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for jumping jacks exercise"""
    try:
        # Extract key landmarks
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_elbow = landmarks[13]
        right_elbow = landmarks[14]
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        left_knee = landmarks[25]
        right_knee = landmarks[26]
        left_ankle = landmarks[27]
        right_ankle = landmarks[28]

        # Check if all landmarks are present and have x, y coordinates
        key_points = [
            left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist,
            left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle
        ]
        
        if not all(point and all(k in point for k in ['x', 'y']) for point in key_points):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera",
                'angles': {}
            }

        # Calculate arm angles (angle between shoulder-elbow-wrist)
        left_arm_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
        right_arm_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)

        # Calculate shoulder angles (angle between hip-shoulder-elbow)
        left_shoulder_angle = calculate_angle(left_hip, left_shoulder, left_elbow)
        right_shoulder_angle = calculate_angle(right_hip, right_shoulder, right_elbow)

        # Calculate leg angles (angle between hip-knee-ankle)
        left_leg_angle = calculate_angle(left_hip, left_knee, left_ankle)
        right_leg_angle = calculate_angle(right_hip, right_knee, right_ankle)

        # Calculate hip angles (angle between shoulder-hip-knee)
        left_hip_angle = calculate_angle(left_shoulder, left_hip, left_knee)
        right_hip_angle = calculate_angle(right_shoulder, right_hip, right_knee)

        # Store angles for display with positions
        angles = {
            'LArm': {
                'value': left_arm_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            },
            'RArm': {
                'value': right_arm_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            },
            'LShoulder': {
                'value': left_shoulder_angle,
                'position': {
                    'x': left_shoulder['x'],
                    'y': left_shoulder['y']
                }
            },
            'RShoulder': {
                'value': right_shoulder_angle,
                'position': {
                    'x': right_shoulder['x'],
                    'y': right_shoulder['y']
                }
            },
            'LLeg': {
                'value': left_leg_angle,
                'position': {
                    'x': left_knee['x'],
                    'y': left_knee['y']
                }
            },
            'RLeg': {
                'value': right_leg_angle,
                'position': {
                    'x': right_knee['x'],
                    'y': right_knee['y']
                }
            },
            'LHip': {
                'value': left_hip_angle,
                'position': {
                    'x': left_hip['x'],
                    'y': left_hip['y']
                }
            },
            'RHip': {
                'value': right_hip_angle,
                'position': {
                    'x': right_hip['x'],
                    'y': right_hip['y']
                }
            }
        }

        # Detect jumping jack phases using angles
        # Closed position: Arms down (large arm angle, small shoulder angle) and legs together (large leg angle, small hip angle)
        is_closed_position = (
            left_arm_angle > 150 and right_arm_angle > 150 and
            left_shoulder_angle < 50 and right_shoulder_angle < 50 and
            left_leg_angle > 160 and right_leg_angle > 160 and
            left_hip_angle < 30 and right_hip_angle < 30
        )

        # Open position: Arms up (small arm angle, large shoulder angle) and legs apart (small leg angle, large hip angle)
        is_open_position = (
            left_arm_angle < 120 and right_arm_angle < 120 and
            left_shoulder_angle > 160 and right_shoulder_angle > 160 and
            left_leg_angle < 140 and right_leg_angle < 140 and
            left_hip_angle > 50 and right_hip_angle > 50
        )

        feedback = ""
        if is_closed_position:
            state['stage'] = "closed"
            state['holdStart'] = current_time
            feedback = "Closed position - prepare to jump"

        if is_open_position and state['stage'] == "closed":
            if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                state['stage'] = "open"
                state['repCounter'] += 1
                state['lastRepTime'] = current_time
                feedback = "Rep complete! Good jumping jack."
            else:
                feedback = "Open position - good form"
        
        if not is_open_position and not is_closed_position:
            feedback = "Transition - continue your movement"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in jumping jacks detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


def process_lunge(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for lunge exercise"""
    try:
        # Get landmarks for both sides of the body
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        left_ankle = landmarks[27]
        right_hip = landmarks[24]
        right_knee = landmarks[26]
        right_ankle = landmarks[28]

        # Check if all landmarks are present with x, y coordinates
        if not all(
            point and all(k in point for k in ['x', 'y']) 
            for point in [left_hip, left_knee, left_ankle, right_hip, right_knee, right_ankle]
        ):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera",
                'angles': {}
            }

        # Calculate leg angles for both sides
        left_leg_angle = calculate_angle(
            {'x': left_hip['x'], 'y': left_hip['y']},
            {'x': left_knee['x'], 'y': left_knee['y']},
            {'x': left_ankle['x'], 'y': left_ankle['y']}
        )

        right_leg_angle = calculate_angle(
            {'x': right_hip['x'], 'y': right_hip['y']},
            {'x': right_knee['x'], 'y': right_knee['y']},
            {'x': right_ankle['x'], 'y': right_ankle['y']}
        )

        # Calculate vertical distance between knees to detect lunge position
        knee_height_diff = abs(left_knee['y'] - right_knee['y'])

        # Determine which leg is in front (lower knee is the front leg)
        front_leg_angle = right_leg_angle if left_knee['y'] > right_knee['y'] else left_leg_angle
        back_leg_angle = left_leg_angle if left_knee['y'] > right_knee['y'] else right_leg_angle
        front_knee = right_knee if left_knee['y'] > right_knee['y'] else left_knee
        back_knee = left_knee if left_knee['y'] > right_knee['y'] else right_knee
        
        # Store angles for display with positions
        angles = {
            'LLeg': {
                'value': left_leg_angle,
                'position': {
                    'x': left_knee['x'],
                    'y': left_knee['y']
                }
            },
            'RLeg': {
                'value': right_leg_angle,
                'position': {
                    'x': right_knee['x'],
                    'y': right_knee['y']
                }
            },
            'Front': {
                'value': front_leg_angle,
                'position': {
                    'x': front_knee['x'],
                    'y': front_knee['y']
                }
            },
            'Back': {
                'value': back_leg_angle,
                'position': {
                    'x': back_knee['x'],
                    'y': back_knee['y']
                }
            },
            'KneeDiff': {
                'value': knee_height_diff * 100,  # Convert to percentage
                'position': {
                    'x': (left_knee['x'] + right_knee['x']) / 2,
                    'y': (left_knee['y'] + right_knee['y']) / 2
                }
            }
        }

        # Track standing position - both legs relatively straight
        feedback = ""
        if (left_leg_angle > 150 and right_leg_angle > 150) and knee_height_diff < 0.1:
            state['stage'] = "up"
            state['holdStart'] = current_time
            feedback = "Standing position - prepare for lunge"

        # Proper lunge detection - front leg bent, back leg straighter, significant height difference
        proper_front_angle = front_leg_angle < 110  # Front knee should be bent (~90° is ideal)
        proper_back_angle = back_leg_angle > 130    # Back leg should be straighter
        proper_knee_height = knee_height_diff > 0.2  # Sufficient height difference between knees

        if proper_front_angle and proper_back_angle and proper_knee_height and state['stage'] == "up":
            if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                state['stage'] = "down"
                state['repCounter'] += 1
                state['lastRepTime'] = current_time
                feedback = "Rep complete! Good lunge."
            else:
                feedback = "Lunge position - hold it"
        
        # Form feedback
        if state['stage'] == "down" and not proper_front_angle:
            feedback = "Bend your front knee more"
        elif state['stage'] == "down" and not proper_back_angle:
            feedback = "Keep your back leg straighter"
        elif state['stage'] == "up" and knee_height_diff > 0.1:
            feedback = "Stand with feet together"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in lunge detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }


# Run the app
if __name__ == '__main__':
    # Get port from environment variable or use default (8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
