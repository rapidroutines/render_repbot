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
        elif exercise_type == 'tricepExtension':
            result = process_tricep_extension(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'lunge':
            result = process_lunge(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        elif exercise_type == 'calfRaises':  # Add this new condition
            result = process_calf_raises(landmarks, client_state, current_time, rep_cooldown, hold_threshold)
        
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
            if left_angle > 140:
                state['leftArmStage'] = "down"
                state['leftArmHoldStart'] = current_time
            if left_angle < 50 and state['leftArmStage'] == "down":
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
            if right_angle > 140:
                state['rightArmStage'] = "down"
                state['rightArmHoldStart'] = current_time
            if right_angle < 50 and state['rightArmStage'] == "down":
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
    """Process landmarks for shoulder press exercise with improved rep counting"""
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
        feedback = ""

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

        # Process shoulder press detection with improved state machine
        if avg_elbow_angle is not None:
            # IMPROVED LOGIC: More clearly define the "up" and "down" positions
            
            # DOWN POSITION: Arms bent, wrists at or below shoulders
            in_down_position = avg_elbow_angle < 100 and both_wrists_below_shoulder
            
            # UP POSITION: Arms extended, wrists above shoulders
            in_up_position = (avg_elbow_angle > 140 and both_wrists_above_shoulder) or (avg_elbow_angle > 150 and one_wrist_above_shoulder)
            
            # STATE TRANSITIONS with clearer logic
            if in_down_position:
                # If we were previously in the up position and now in down, we're ready for next rep
                if state['stage'] == "up":
                    # Reset to down position, ready for next rep
                    state['stage'] = "down"
                    feedback = "Ready for next rep"
                elif state['stage'] == "down":
                    # Already in down position
                    feedback = "Ready position - good start"
                
                # Always reset the hold timer when in down position
                state['holdStart'] = current_time
                
            elif in_up_position:
                # If we were in down position and now reaching up, check for a rep
                if state['stage'] == "down":
                    # Only count if enough time has passed since the last rep
                    if current_time - state['lastRepTime'] > rep_cooldown:
                        state['repCounter'] += 1
                        state['lastRepTime'] = current_time
                        state['stage'] = "up"
                        feedback = "Rep complete! Good press."
                    else:
                        # Still in cooldown period
                        feedback = "Slow down a bit"
                elif state['stage'] == "up":
                    # Already in up position
                    feedback = "Lower arms to start next rep"
            
            # FORM FEEDBACK
            elif state['stage'] == "down" and avg_elbow_angle < 65:
                feedback = "Start with arms higher"
            elif one_wrist_above_shoulder and not both_wrists_above_shoulder:
                feedback = "Press both arms evenly"
            elif not feedback:
                # In-between positions
                if state['stage'] == "up":
                    feedback = "Lower arms completely"
                else:
                    feedback = "Continue the movement"

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

def process_tricep_extension(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for floor tricep extension exercise"""
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
        left_extension_detected = False
        right_extension_detected = False
        angles = {}
        feedback = ""

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

            # Detect left arm extension
            if left_angle < 100:  # Arm is bent (starting position)
                state['leftArmStage'] = "down"
                state['leftArmHoldStart'] = current_time
            if left_angle > 140 and state['leftArmStage'] == "down":  # Arm is extended
                if current_time - state['leftArmHoldStart'] > hold_threshold:
                    left_extension_detected = True
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

            # Detect right arm extension
            if right_angle < 100:  # Arm is bent (starting position)
                state['rightArmStage'] = "down"
                state['rightArmHoldStart'] = current_time
            if right_angle > 140 and state['rightArmStage'] == "down":  # Arm is extended
                if current_time - state['rightArmHoldStart'] > hold_threshold:
                    right_extension_detected = True
                    state['rightArmStage'] = "up"

        # Count rep only if both arms complete an extension and enough time has passed since last rep
        if (left_extension_detected and right_extension_detected) and current_time - state['lastRepTime'] > rep_cooldown:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time
            feedback = "Good rep! Both arms extended."
        else:
            # Simple feedback
            if left_extension_detected and not right_extension_detected:
                feedback = "Extend your right arm too"
            elif not left_extension_detected and right_extension_detected:
                feedback = "Extend your left arm too"

        return {
            'repCounter': state['repCounter'],
            'stage': 'up' if (left_extension_detected and right_extension_detected) else 'down',
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in tricep extension detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}"
        }

def process_lunge(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for lunge exercise with more lenient detection criteria"""
    try:
        # Get landmarks for both sides of the body
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        left_ankle = landmarks[27]
        right_hip = landmarks[24]
        right_knee = landmarks[26]
        right_ankle = landmarks[28]

        # Check if all landmarks are present with x, y coordinates
        all_landmarks_visible = all(
            point and all(k in point for k in ['x', 'y']) 
            for point in [left_hip, left_knee, left_ankle, right_hip, right_knee, right_ankle]
        )
        
        # Partial visibility check - at least one leg should be fully visible
        left_leg_visible = all(k in point for k in ['x', 'y'] 
                              for point in [left_hip, left_knee, left_ankle])
        right_leg_visible = all(k in point for k in ['x', 'y'] 
                               for point in [right_hip, right_knee, right_ankle])
        
        if not (left_leg_visible or right_leg_visible):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position not clear - adjust camera",
                'angles': {}
            }

        angles = {}
        left_leg_angle = None
        right_leg_angle = None
        
        # Calculate leg angles for both sides if landmarks are visible
        if left_leg_visible:
            left_leg_angle = calculate_angle(
                {'x': left_hip['x'], 'y': left_hip['y']},
                {'x': left_knee['x'], 'y': left_knee['y']},
                {'x': left_ankle['x'], 'y': left_ankle['y']}
            )
            angles['LLeg'] = {
                'value': left_leg_angle,
                'position': {
                    'x': left_knee['x'],
                    'y': left_knee['y']
                }
            }

        if right_leg_visible:
            right_leg_angle = calculate_angle(
                {'x': right_hip['x'], 'y': right_hip['y']},
                {'x': right_knee['x'], 'y': right_knee['y']},
                {'x': right_ankle['x'], 'y': right_ankle['y']}
            )
            angles['RLeg'] = {
                'value': right_leg_angle,
                'position': {
                    'x': right_knee['x'],
                    'y': right_knee['y']
                }
            }

        # If both knees are visible, calculate height difference
        knee_height_diff = 0
        if all_landmarks_visible:
            knee_height_diff = abs(left_knee['y'] - right_knee['y'])
            angles['KneeDiff'] = {
                'value': knee_height_diff * 100,  # Convert to percentage for display
                'position': {
                    'x': (left_knee['x'] + right_knee['x']) / 2,
                    'y': (left_knee['y'] + right_knee['y']) / 2
                }
            }

        # Determine which leg is in front (lower knee is the front leg)
        front_leg_angle = None
        back_leg_angle = None
        front_knee = None
        back_knee = None

        if all_landmarks_visible:
            if left_knee['y'] > right_knee['y']:  # Right knee is higher (in front in image coordinates)
                front_leg_angle = right_leg_angle
                back_leg_angle = left_leg_angle
                front_knee = right_knee
                back_knee = left_knee
            else:  # Left knee is higher (in front in image coordinates)
                front_leg_angle = left_leg_angle
                back_leg_angle = right_leg_angle
                front_knee = left_knee
                back_knee = right_knee
                
            # Add these angles to the display data
            if front_leg_angle is not None and back_leg_angle is not None:
                angles['Front'] = {
                    'value': front_leg_angle,
                    'position': {
                        'x': front_knee['x'],
                        'y': front_knee['y']
                    }
                }
                angles['Back'] = {
                    'value': back_leg_angle,
                    'position': {
                        'x': back_knee['x'],
                        'y': back_knee['y']
                    }
                }

        # Track standing position - both legs relatively straight (more lenient)
        feedback = ""
        
        # MORE LENIENT: Allow standing detection with just one visible leg if it's straight
        standing_detected = False
        if all_landmarks_visible:
            # Both legs visible - check if both are straight-ish and knees are at similar height
            standing_detected = (left_leg_angle > 140 and right_leg_angle > 140) and knee_height_diff < 0.15
        elif left_leg_visible and left_leg_angle > 140:
            # Only left leg visible and it's straight
            standing_detected = True
        elif right_leg_visible and right_leg_angle > 140:
            # Only right leg visible and it's straight
            standing_detected = True
            
        if standing_detected:
            state['stage'] = "up"
            state['holdStart'] = current_time
            feedback = "Standing position - prepare for lunge"

        # Proper lunge detection - MORE LENIENT CRITERIA
        lunge_detected = False
        
        # If all landmarks are visible, use comprehensive criteria
        if all_landmarks_visible and front_leg_angle is not None and back_leg_angle is not None:
            # MORE LENIENT: Front leg doesn't need to be as bent, back leg can be more relaxed
            proper_front_angle = front_leg_angle < 130  # Was 110, now 130 (more lenient)
            proper_back_angle = back_leg_angle > 120    # Was 130, now 120 (more lenient)
            proper_knee_height = knee_height_diff > 0.15  # Was 0.2, now 0.15 (more lenient)
            
            lunge_detected = proper_front_angle and proper_back_angle and proper_knee_height
        # MORE LENIENT: Allow detecting lunges with single leg visibility
        elif left_leg_visible and left_leg_angle < 130:
            # Left leg is bent enough to potentially be in lunge position
            lunge_detected = True
        elif right_leg_visible and right_leg_angle < 130:
            # Right leg is bent enough to potentially be in lunge position
            lunge_detected = True
            
        if lunge_detected and state['stage'] == "up":
            if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                state['stage'] = "down"
                state['repCounter'] += 1
                state['lastRepTime'] = current_time
                feedback = "Rep complete! Good lunge."
            else:
                feedback = "Lunge position - hold it"
        
        # Simplified feedback - less critical of form
        if state['stage'] == "down" and not feedback:
            feedback = "Return to standing position"
        elif state['stage'] == "up" and knee_height_diff > 0.15 and not feedback:
            feedback = "Prepare for next lunge"

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


def process_calf_raises(landmarks, state, current_time, rep_cooldown, hold_threshold):
    """Process landmarks for calf raises exercise"""
    try:
        # Get landmarks for ankles, knees, and hips
        left_ankle = landmarks[27]
        right_ankle = landmarks[28]
        left_knee = landmarks[25]
        right_knee = landmarks[26]
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        left_heel = landmarks[29]  # MediaPipe provides heel landmarks
        right_heel = landmarks[30]
        left_foot_index = landmarks[31]  # Toe point
        right_foot_index = landmarks[32]

        # Track vertical positions for analysis
        angles = {}
        feedback = ""
        
        # Check if all required landmarks are visible
        if not all(point and all(k in point for k in ['x', 'y']) 
                  for point in [left_ankle, right_ankle, left_knee, right_knee]):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Position feet in view of camera",
                'angles': {}
            }
        
        # Calculate ankle-heel height difference for both feet
        # This measures how high the heel is lifted relative to the ankle
        left_heel_lift = 0
        right_heel_lift = 0
        
        if all(k in left_heel for k in ['x', 'y']) and all(k in left_ankle for k in ['x', 'y']):
            left_heel_lift = left_ankle['y'] - left_heel['y']
            angles['LHeelLift'] = {
                'value': left_heel_lift * 100,  # Convert to percentage for display
                'position': {
                    'x': left_ankle['x'],
                    'y': left_ankle['y'] + 0.05  # Position slightly below ankle
                }
            }
        
        if all(k in right_heel for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y']):
            right_heel_lift = right_ankle['y'] - right_heel['y']
            angles['RHeelLift'] = {
                'value': right_heel_lift * 100,  # Convert to percentage for display
                'position': {
                    'x': right_ankle['x'],
                    'y': right_ankle['y'] + 0.05  # Position slightly below ankle
                }
            }
            
        # Calculate ankle-to-toe angle (foot extension)
        left_foot_angle = None
        right_foot_angle = None
        
        if all(k in left_ankle for k in ['x', 'y']) and all(k in left_heel for k in ['x', 'y']) and all(k in left_foot_index for k in ['x', 'y']):
            left_foot_angle = calculate_angle(left_heel, left_ankle, left_foot_index)
            angles['LFootAngle'] = {
                'value': left_foot_angle,
                'position': {
                    'x': left_ankle['x'] - 0.05,  # Position slightly to the left of ankle
                    'y': left_ankle['y']
                }
            }
            
        if all(k in right_ankle for k in ['x', 'y']) and all(k in right_heel for k in ['x', 'y']) and all(k in right_foot_index for k in ['x', 'y']):
            right_foot_angle = calculate_angle(right_heel, right_ankle, right_foot_index)
            angles['RFootAngle'] = {
                'value': right_foot_angle,
                'position': {
                    'x': right_ankle['x'] + 0.05,  # Position slightly to the right of ankle
                    'y': right_ankle['y']
                }
            }
        
        # Calculate average calf raise height and foot angle
        avg_heel_lift = 0
        if left_heel_lift > 0 and right_heel_lift > 0:
            avg_heel_lift = (left_heel_lift + right_heel_lift) / 2
        elif left_heel_lift > 0:
            avg_heel_lift = left_heel_lift
        elif right_heel_lift > 0:
            avg_heel_lift = right_heel_lift
            
        avg_foot_angle = 0
        if left_foot_angle is not None and right_foot_angle is not None:
            avg_foot_angle = (left_foot_angle + right_foot_angle) / 2
        elif left_foot_angle is not None:
            avg_foot_angle = left_foot_angle
        elif right_foot_angle is not None:
            avg_foot_angle = right_foot_angle
            
        # Add average metrics to display data
        if avg_heel_lift > 0:
            angles['AvgLift'] = {
                'value': avg_heel_lift * 100,  # Convert to percentage
                'position': {
                    'x': (left_ankle['x'] + right_ankle['x']) / 2,
                    'y': (left_ankle['y'] + right_ankle['y']) / 2 + 0.1
                }
            }
        
        # Check body stability (knees and hips should remain relatively stable)
        knee_stability = True
        if all(k in left_knee for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y']):
            knee_vertical_diff = abs(left_knee['y'] - right_knee['y'])
            if knee_vertical_diff > 0.05:  # If knees are at very different heights
                knee_stability = False
                
        # Process calf raise detection
        # "down" = flat feet, "up" = raised heels
        
        # Flat feet detection (down position)
        if avg_heel_lift < 0.01:  # Very small lift indicates flat feet
            state['stage'] = "down"
            state['holdStart'] = current_time
            feedback = "Starting position - feet flat"
        
        # Raised heels detection (up position)
        # Check if heels are raised AND foot is at proper angle
        heel_raised = avg_heel_lift > 0.02  # Threshold for heel raise detection
        good_foot_angle = avg_foot_angle < 80 if avg_foot_angle > 0 else False  # Foot should be at proper angle
        
        if heel_raised and good_foot_angle and state['stage'] == "down":
            if current_time - state['holdStart'] > hold_threshold and current_time - state['lastRepTime'] > rep_cooldown:
                state['stage'] = "up"
                state['repCounter'] += 1
                state['lastRepTime'] = current_time
                
                # Provide feedback on form
                if not knee_stability:
                    feedback = "Rep counted! Try to keep knees steady."
                else:
                    feedback = "Good rep! Nice calf raise."
            else:
                feedback = "Raised position - hold briefly"
                
        # Form feedback
        if state['stage'] == "up" and not feedback:
            feedback = "Lower heels completely to floor"
        elif state['stage'] == "down" and heel_raised and not good_foot_angle:
            feedback = "Rise up on the balls of your feet"
        elif not knee_stability:
            feedback = "Keep knees steady and even"
            
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': feedback,
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in calf raise detection: {str(e)}")
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
