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


def process_bicep_curl(landmarks, state, current_time, rep_cooldown, hold_threshold):    #working
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
            # More lenient: Changed from 160 to 150 degrees
            if avg_knee_angle > 150 and hip_height < 0.6:
                state['stage'] = "up"
                state['holdStart'] = current_time
                feedback = "Standing position"
            
            # Squat position detection (bent knees and lower hip position)
            # More lenient: Changed from 120 to 130 degrees, and hip height from 0.65 to 0.6
            if avg_knee_angle < 130 and hip_height > 0.6 and state['stage'] == "up":
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

def process_pushup(landmarks, state, current_time, rep_cooldown, hold_threshold):  #working
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
            # More lenient: Changed from 15 to 20 degrees
            if body_alignment > 20:
                warnings.append("Keep body straight!")

        # Process pushup detection using elbow angles, body height, and alignment
        status = ""
        if avg_elbow_angle is not None and body_height is not None:
            # Up position detection (straight arms, higher body position)
            # More lenient: Changed from 160 to 150 degrees, and body height from 0.7 to 0.75
            if avg_elbow_angle > 150 and body_height < 0.75:
                state['stage'] = "up"
                state['holdStart'] = current_time
                status = "Up Position"

            # Down position detection (bent arms, lower body position)
            # More lenient: Changed from 90 to 100 degrees
            if avg_elbow_angle < 100 and state['stage'] == "up":
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
    """Process landmarks for shoulder press exercise"""
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
        left_press_detected = False
        right_press_detected = False
        angles = {}
        
        # Calculate and store left arm angle
        if all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y']):
            left_angle = calculate_angle(left_wrist, left_elbow, left_shoulder)
            
            # Store angle with position data
            angles['L'] = {
                'value': left_angle,
                'position': {
                    'x': left_elbow['x'],
                    'y': left_elbow['y']
                }
            }
            
            # Detect left arm press
            if left_angle > 150:
                state['leftArmStage'] = "down"
            
            if left_angle < 60 and state.get('leftArmStage') == "down":
                left_press_detected = True
                state['leftArmStage'] = "up"
        
        # Calculate and store right arm angle
        if all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y']):
            right_angle = calculate_angle(right_wrist, right_elbow, right_shoulder)
            
            # Store angle with position data
            angles['R'] = {
                'value': right_angle,
                'position': {
                    'x': right_elbow['x'],
                    'y': right_elbow['y']
                }
            }
            
            # Detect right arm press
            if right_angle > 150:
                state['rightArmStage'] = "down"
            
            if right_angle < 60 and state.get('rightArmStage') == "down":
                right_press_detected = True
                state['rightArmStage'] = "up"
        
        # Count rep if either arm completes a press
        if left_press_detected or right_press_detected:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time
            
            # Simple feedback
            feedback = "Rep complete!"
            
            return {
                'repCounter': state['repCounter'],
                'stage': 'up' if left_press_detected or right_press_detected else 'down',
                'feedback': feedback,
                'angles': angles
            }
        
        # Return current state if no rep detected
        return {
            'repCounter': state['repCounter'],
            'stage': state.get('leftArmStage', 'down') if left_angle is not None else state.get('rightArmStage', 'down'),
            'angles': angles
        }
        
    except Exception as e:
        print(f"Error in shoulder press detection: {str(e)}")
        return {
            'repCounter': state.get('repCounter', 0),
            'stage': state.get('stage', 'down'),
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
            # For tricep extensions: bent arm is "down", straight arm is "up"
            if left_angle < 110:  # Arm is bent (starting position) - more lenient threshold
                if state['leftArmStage'] != "down":
                    feedback = "Left arm ready position"
                state['leftArmStage'] = "down"
                state['leftArmHoldStart'] = current_time
            elif left_angle > 140 and state['leftArmStage'] == "down":  # Arm is extended - more lenient threshold
                if current_time - state['leftArmHoldStart'] > hold_threshold:
                    left_extension_detected = True
                    state['leftArmStage'] = "up"
                    feedback = "Left arm extended"

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
            if right_angle < 110:  # Arm is bent (starting position) - more lenient threshold
                if state['rightArmStage'] != "down":
                    feedback = "Right arm ready position"
                state['rightArmStage'] = "down"
                state['rightArmHoldStart'] = current_time
            elif right_angle > 140 and state['rightArmStage'] == "down":  # Arm is extended - more lenient threshold
                if current_time - state['rightArmHoldStart'] > hold_threshold:
                    right_extension_detected = True
                    state['rightArmStage'] = "up"
                    feedback = "Right arm extended"

        # Calculate average arm angle if both are available
        if left_angle is not None and right_angle is not None:
            avg_angle = (left_angle + right_angle) / 2
            # Position between both elbows
            mid_x = (left_elbow['x'] + right_elbow['x']) / 2
            mid_y = (left_elbow['y'] + right_elbow['y']) / 2
            angles['Avg'] = {
                'value': avg_angle,
                'position': {
                    'x': mid_x,
                    'y': mid_y - 0.05  # Offset upward
                }
            }

        # Count rep if either arm completes an extension and enough time has passed since last rep
        if (left_extension_detected or right_extension_detected) and current_time - state['lastRepTime'] > rep_cooldown:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time
            
            # Generate feedback
            if left_extension_detected and right_extension_detected:
                feedback = "Great form! Both arms extended fully."
            elif left_extension_detected:
                feedback = "Left arm extension complete."
            elif right_extension_detected:
                feedback = "Right arm extension complete."

        # Always include the current stage in the response
        return {
            'repCounter': state['repCounter'],
            'stage': state['leftArmStage'] if left_angle is not None else (state['rightArmStage'] if right_angle is not None else state['stage']),
            'feedback': feedback,
            'angles': angles,
            'status': f"L:{state['leftArmStage']} R:{state['rightArmStage']}" # Debug info
        }
        
    except Exception as e:
        print(f"Error in tricep extension detection: {str(e)}")
        return {
            'repCounter': state['repCounter'],
            'stage': state['stage'],
            'feedback': f"Error: {str(e)}",
            'angles': {}
        }

def process_lunge(landmarks, state, current_time, rep_cooldown, hold_threshold): #working
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
        # More lenient: Changed from 150 to 140 degrees, and knee height diff from 0.1 to 0.15
        feedback = ""
        if (left_leg_angle > 140 and right_leg_angle > 140) and knee_height_diff < 0.15:
            state['stage'] = "up"
            state['holdStart'] = current_time
            feedback = "Standing position - prepare for lunge"

        # Proper lunge detection - front leg bent, back leg straighter, significant height difference
        # More lenient: Changed front knee angle from 110 to 120, back knee angle from 130 to 120,
        # and knee height difference from 0.2 to 0.15
        proper_front_angle = front_leg_angle < 120  # Front knee should be bent (~90° is ideal)
        proper_back_angle = back_leg_angle > 120    # Back leg should be straighter
        proper_knee_height = knee_height_diff > 0.15  # Sufficient height difference between knees

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
        elif state['stage'] == "up" and knee_height_diff > 0.15:
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


# Run the app
if __name__ == '__main__':
    # Get port from environment variable or use default (8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
