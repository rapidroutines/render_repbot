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
    """Process landmarks for squat exercise using similar logic to the JavaScript implementation"""
    try:
        # Get landmarks for both legs
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        left_ankle = landmarks[27]
        right_hip = landmarks[24]
        right_knee = landmarks[26]
        right_ankle = landmarks[28]

        # Variables to store angles and status
        left_knee_angle = None
        right_knee_angle = None
        avg_knee_angle = None
        hip_height = None
        angles = {}
        feedback = ""

        # Calculate left knee angle if landmarks are visible
        if all(k in left_hip for k in ['x', 'y']) and all(k in left_knee for k in ['x', 'y']) and all(k in left_ankle for k in ['x', 'y']):
            left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            angles['L'] = {
                'value': left_knee_angle,
                'position': {
                    'x': left_knee['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': left_knee['y']
                }
            }

        # Calculate right knee angle if landmarks are visible
        if all(k in right_hip for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y']):
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
            angles['R'] = {
                'value': right_knee_angle,
                'position': {
                    'x': right_knee['x'] + 0.05,  # Offset a bit to the right like in JS
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
                    'y': mid_y - 0.05  # Offset upward like in JS
                }
            }
        elif left_knee_angle is not None:
            avg_knee_angle = left_knee_angle
        elif right_knee_angle is not None:
            avg_knee_angle = right_knee_angle

        # Calculate hip height (normalized to image height)
        if all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y']):
            hip_height = (left_hip['y'] + right_hip['y']) / 2
            mid_x = (left_hip['x'] + right_hip['x']) / 2
            angles['Hip'] = {
                'value': hip_height * 100,  # Convert to percentage
                'position': {
                    'x': mid_x,
                    'y': hip_height - 0.05  # Offset upward like in JS
                }
            }

        # Process squat detection using both knee angles and hip height
        if avg_knee_angle is not None and hip_height is not None:
            # Standing position detection (straight legs and higher hip position)
            if avg_knee_angle > 160 and hip_height < 0.6:
                state['stage'] = "up"
                state['holdStart'] = current_time
                feedback = "Standing position"
            
            # Squat position detection (bent knees and lower hip position)
            if avg_knee_angle < 120 and hip_height > 0.65 and state['stage'] == "up":
                if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "down"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    feedback = "Rep complete!"
                else:
                    feedback = "Squatting"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles,
            'status': "Standing" if state['stage'] == "up" else "Squatting"  # Include status for UI display
        }
        
    except Exception as e:
        print(f"Error in squat detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {}
        }

def process_pushup(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for pushup exercise using similar logic to the JavaScript implementation"""
    try:
        # Get landmarks for both arms and shoulders
        left_shoulder = landmarks[11]
        left_elbow = landmarks[13]
        left_wrist = landmarks[15]
        right_shoulder = landmarks[12]
        right_elbow = landmarks[14]
        right_wrist = landmarks[16]

        # Additional body points for height/position tracking
        nose = landmarks[0]
        left_hip = landmarks[23]
        right_hip = landmarks[24]

        # Variables to store angles and status
        left_elbow_angle = None
        right_elbow_angle = None
        avg_elbow_angle = None
        body_height = None
        body_alignment = None
        angles = {}
        feedback = ""
        warnings = []

        # Calculate left arm angle if landmarks are visible
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
            angles['L'] = {
                'value': left_elbow_angle,
                'position': {
                    'x': left_elbow['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': left_elbow['y']
                }
            }

        # Calculate right arm angle if landmarks are visible
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
            angles['R'] = {
                'value': right_elbow_angle,
                'position': {
                    'x': right_elbow['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': right_elbow['y']
                }
            }

        # Calculate average elbow angle if both are available
        if left_elbow_angle is not None and right_elbow_angle is not None:
            avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2
            # Position between both elbows
            mid_x = (left_elbow['x'] + right_elbow['x']) / 2
            mid_y = (left_elbow['y'] + right_elbow['y']) / 2
            angles['Avg'] = {
                'value': avg_elbow_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y - 0.05  # Offset upward like in JS
                }
            }
        elif left_elbow_angle is not None:
            avg_elbow_angle = left_elbow_angle
        elif right_elbow_angle is not None:
            avg_elbow_angle = right_elbow_angle

        # Calculate body height (y-coordinate of shoulders)
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']):
            body_height = (left_shoulder['y'] + right_shoulder['y']) / 2
            mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
            angles['Height'] = {
                'value': body_height * 100,  # Convert to percentage
                'position': {
                    'x': mid_x,
                    'y': body_height - 0.05  # Offset upward like in JS
                }
            }

        # Check body alignment (straight back)
        if (all(k in left_shoulder for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']) and 
            all(k in left_hip for k in ['x', 'y']) and all(k in right_hip for k in ['x', 'y'])):
            
            shoulder_mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
            shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
            hip_mid_x = (left_hip['x'] + right_hip['x']) / 2
            hip_mid_y = (left_hip['y'] + right_hip['y']) / 2

            # Calculate angle between shoulders and hips to check for body alignment
            alignment_angle = math.atan2(hip_mid_y - shoulder_mid_y, hip_mid_x - shoulder_mid_x) * 180 / math.pi
            alignment_angle = abs(alignment_angle)

            # Normalize to 0-90 degree range (0 = perfect horizontal alignment)
            if alignment_angle > 90:
                alignment_angle = 180 - alignment_angle

            body_alignment = alignment_angle
            angles['Align'] = {
                'value': body_alignment,
                'position': {
                    'x': hip_mid_x,
                    'y': hip_mid_y + 0.05  # Offset downward like in JS
                }
            }
            
            # Check alignment and add warning if needed
            if body_alignment > 15:
                warnings.append("Keep body straight!")

        # Process pushup detection using elbow angles, body height, and alignment
        status = ""
        if avg_elbow_angle is not None and body_height is not None:
            # Up position detection (straight arms, higher body position)
            if avg_elbow_angle > 160 and body_height < 0.7:
                state['stage'] = "up"
                state['holdStart'] = current_time
                status = "Up Position"

            # Down position detection (bent arms, lower body position)
            if avg_elbow_angle < 90 and state['stage'] == "up":
                if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "down"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    status = "Rep Complete!"
                    feedback = "Rep complete! Good pushup."
                else:
                    status = "Down Position"
                    feedback = "Down position - hold briefly"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles,
            'status': status,
            'warnings': warnings
        }
        
    except Exception as e:
        print(f"Error in pushup detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {},
            'status': "",
            'warnings': []
        }


def process_shoulder_press(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for shoulder press exercise with proper rep counting"""
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
        positions = {}
        feedback = ""
        warnings = []

        # Calculate left arm position and angle
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_elbow_angle = calculate_angle(left_wrist, left_elbow, left_shoulder)
            
            # Check if left wrist is above shoulder
            left_wrist_above_shoulder = left_wrist['y'] < left_shoulder['y']
            
            # Store angle with position data
            angles['L'] = {
                'value': left_elbow_angle,
                'position': {
                    'x': left_elbow['x'] + 0.05,
                    'y': left_elbow['y']
                }
            }
            
            # Store wrist position indicator
            positions['LWrist'] = {
                'value': "↑" if left_wrist_above_shoulder else "↓",
                'position': {
                    'x': left_wrist['x'],
                    'y': left_wrist['y'] - 0.02
                },
                'color': "#00FF00" if left_wrist_above_shoulder else "#FF9900"
            }

        # Calculate right arm position and angle
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_elbow_angle = calculate_angle(right_wrist, right_elbow, right_shoulder)
            
            # Check if right wrist is above shoulder
            right_wrist_above_shoulder = right_wrist['y'] < right_shoulder['y']
            
            # Store angle with position data
            angles['R'] = {
                'value': right_elbow_angle,
                'position': {
                    'x': right_elbow['x'] + 0.05,
                    'y': right_elbow['y']
                }
            }
            
            # Store wrist position indicator
            positions['RWrist'] = {
                'value': "↑" if right_wrist_above_shoulder else "↓",
                'position': {
                    'x': right_wrist['x'],
                    'y': right_wrist['y'] - 0.02
                },
                'color': "#00FF00" if right_wrist_above_shoulder else "#FF9900"
            }

        # Calculate average elbow angle if both are available
        avg_elbow_angle = None
        if left_elbow_angle is not None and right_elbow_angle is not None:
            avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2
            
            # Store average angle with position between elbows
            angles['Avg'] = {
                'value': avg_elbow_angle,
                'position': {
                    'x': (left_elbow['x'] + right_elbow['x']) / 2,
                    'y': (left_elbow['y'] + right_elbow['y']) / 2 - 0.05
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
        status = ""
        if avg_elbow_angle is not None:
            # Starting (down) position - arms bent, wrists below shoulders
            if avg_elbow_angle < 100 and both_wrists_below_shoulder:
                # Only reset to down if we were previously up
                # This is key for the press cycle to work properly
                if state['stage'] == "up":
                    state['stage'] = "down"
                    state['holdStart'] = current_time
                    
                # If we're already in down stage, just update status
                if state['stage'] == "down":
                    status = "Ready Position"
                    feedback = "Ready position - good start"

            # Up position - arms extended, wrists above shoulders
            if avg_elbow_angle > 140 and (both_wrists_above_shoulder or (one_wrist_above_shoulder and avg_elbow_angle > 150)):
                if state['stage'] == "down" and current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "up"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    status = "Rep Complete!"
                    feedback = "Rep complete! Good press."
                elif state['stage'] == "up":
                    status = "Press Complete"
                    feedback = "Press complete - now return to starting position"

            # Form feedback
            if state['stage'] == "down" and avg_elbow_angle < 65:
                warnings.append("Start higher!")
                feedback = "Start with arms higher"

            if one_wrist_above_shoulder and not both_wrists_above_shoulder and state['stage'] == "up":
                warnings.append("Press both arms evenly!")
                feedback = "Press both arms evenly"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles,
            'positions': positions,
            'status': status,
            'warnings': warnings
        }
        
    except Exception as e:
        print(f"Error in shoulder press detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {},
            'positions': {},
            'status': "",
            'warnings': []
        }

def process_handstand(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for handstand exercise using similar logic to the JavaScript implementation"""
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
                'feedback': "Move to ensure full body is visible",
                'angles': {},
                'form_feedback': {}
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

        # Store angles for UI display
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

        # Store form feedback data
        form_feedback = {
            'isInverted': is_inverted,
            'leftBodyAngle': left_body_angle,
            'rightBodyAngle': right_body_angle,
            'leftLegAngle': left_leg_angle,
            'rightLegAngle': right_leg_angle,
            'wristDistanceRatio': wrist_distance_ratio,
            'isGoodForm': is_good_form
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
            'angles': angles,
            'form_feedback': form_feedback
        }
        
    except Exception as e:
        print(f"Error in handstand detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {},
            'form_feedback': {}
        }



def process_situp(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for sit-up exercise using similar logic to the JavaScript implementation"""
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
        feedback = ""

        # Check if we have all required landmarks
        if (all(k in left_shoulder for k in ['x', 'y']) and all(k in left_hip for k in ['x', 'y']) and 
            all(k in left_knee for k in ['x', 'y']) and all(k in right_shoulder for k in ['x', 'y']) and 
            all(k in right_hip for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y'])):

            # Calculate angle for left side
            left_angle = calculate_angle(
                {'x': left_shoulder['x'], 'y': left_shoulder['y']},
                {'x': left_hip['x'], 'y': left_hip['y']},
                {'x': left_knee['x'], 'y': left_knee['y']}
            )
            
            # Store angle with position data
            angles['L'] = {
                'value': left_angle,
                'position': {
                    'x': left_hip['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': left_hip['y']
                }
            }

            # Calculate angle for right side
            right_angle = calculate_angle(
                {'x': right_shoulder['x'], 'y': right_shoulder['y']},
                {'x': right_hip['x'], 'y': right_hip['y']},
                {'x': right_knee['x'], 'y': right_knee['y']}
            )
            
            # Store angle with position data
            angles['R'] = {
                'value': right_angle,
                'position': {
                    'x': right_hip['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': right_hip['y'] - 0.05  # Offset upward like in JS
                }
            }

            # Calculate average angle (for more stability)
            avg_angle = (left_angle + right_angle) / 2
            
            # Store average angle
            angles['Avg'] = {
                'value': avg_angle,
                'position': {
                    'x': left_hip['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': left_hip['y'] - 0.1  # Offset upward more like in JS
                }
            }

            # Rep counting logic using average angle for more stability
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
                'angles': angles,
                'status': state['stage']  # Include status for UI display
            }
        else:
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera",
                'angles': {},
                'status': ""
            }
        
    except Exception as e:
        print(f"Error in sit-up detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {},
            'status': ""
        }


def process_jumping_jacks(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for jumping jacks exercise using similar logic to the JavaScript implementation"""
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
                'angles': {},
                'position': ""
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
        mid_shoulder_x = (left_shoulder['x'] + right_shoulder['x']) / 2
        mid_shoulder_y = (left_shoulder['y'] + right_shoulder['y']) / 2
        
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
            },
            'Summary': {
                'value': f"L:{int(left_arm_angle)}° R:{int(right_arm_angle)}°",
                'position': {
                    'x': mid_shoulder_x,
                    'y': mid_shoulder_y - 0.12
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
        position = "TRANSITION"
        
        if is_closed_position:
            state['stage'] = "closed"
            state['holdStart'] = current_time
            feedback = "Closed position - prepare to jump"
            position = "CLOSED"
        
        if is_open_position and state['stage'] == "closed":
            if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                state['stage'] = "open"
                state['repCounter'] += 1
                state['lastRepTime'] = current_time
                feedback = "Rep complete! Good jumping jack."
                position = "OPEN"
            else:
                feedback = "Open position - good form"
                position = "OPEN"
        
        if not is_open_position and not is_closed_position:
            feedback = "Transition - continue your movement"
            position = "TRANSITION"

        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles,
            'position': position
        }
        
    except Exception as e:
        print(f"Error in jumping jacks detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {},
            'position': ""
        }


def process_lunge(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for lunge exercise using similar logic to the JavaScript implementation"""
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
        
        # Store angles for display
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
                    'x': front_knee['x'] + 0.05,  # Offset a bit to the right like in JS
                    'y': front_knee['y']
                }
            },
            'Back': {
                'value': back_leg_angle,
                'position': {
                    'x': back_knee['x'] + 0.05,  # Offset a bit to the right like in JS
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
            'feedback': f"Error: {str(e)}",
            'angles': {}
        }


# Run the app
if __name__ == '__main__':
    # Get port from environment variable or use default (8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
