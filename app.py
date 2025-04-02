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
    """Process landmarks for squat exercise with reduced depth requirement"""
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
                    'x': left_knee['x'] + 0.05,  # Offset a bit to the right
                    'y': left_knee['y']
                }
            }

        # Calculate right knee angle if landmarks are visible
        if all(k in right_hip for k in ['x', 'y']) and all(k in right_knee for k in ['x', 'y']) and all(k in right_ankle for k in ['x', 'y']):
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
            angles['R'] = {
                'value': right_knee_angle,
                'position': {
                    'x': right_knee['x'] + 0.05,  # Offset a bit to the right
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
                    'y': mid_y - 0.05  # Offset upward
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
                    'y': hip_height - 0.05  # Offset upward
                }
            }

        # Process squat detection with REDUCED DEPTH REQUIREMENT
        if avg_knee_angle is not None and hip_height is not None:
            # Standing position detection (straight legs and higher hip position)
            # Keep the standing position criteria similar to original
            if avg_knee_angle > 160 and hip_height < 0.6:
                state['stage'] = "up"
                state['holdStart'] = current_time
                feedback = "Standing position"
            
            # MODIFIED: Less deep squat position detection
            # Original required avg_knee_angle < 120 and hip_height > 0.65
            # Now we make it easier by:
            # 1. Increasing the knee angle threshold (less bend required)
            # 2. Reducing the hip height requirement (less depth required)
            if avg_knee_angle < 125 and hip_height > 0.65 and state['stage'] == "up":
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
    """Process landmarks for shoulder press exercise with improved position tracking"""
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
        left_elbow_at_shoulder = False
        right_elbow_at_shoulder = False
        
        # Store wrist positions for vertical movement tracking
        left_wrist_y = None
        right_wrist_y = None
        
        # Add position history tracking if not present in state
        if 'prev_left_wrist_y' not in state:
            state['prev_left_wrist_y'] = None
        if 'prev_right_wrist_y' not in state:
            state['prev_right_wrist_y'] = None
            
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

            # Store current wrist position
            left_wrist_y = left_wrist['y']
            
            # Check if left wrist is above shoulder
            left_wrist_above_shoulder = left_wrist['y'] < left_shoulder['y']
            
            # Check if left elbow is approximately at shoulder height
            left_elbow_at_shoulder = abs(left_elbow['y'] - left_shoulder['y']) < 0.05
            
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

            # Store current wrist position
            right_wrist_y = right_wrist['y']
            
            # Check if right wrist is above shoulder
            right_wrist_above_shoulder = right_wrist['y'] < right_shoulder['y']
            
            # Check if right elbow is approximately at shoulder height
            right_elbow_at_shoulder = abs(right_elbow['y'] - right_shoulder['y']) < 0.05
            
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

        # Determine arm positions 
        both_wrists_above_shoulder = left_wrist_above_shoulder and right_wrist_above_shoulder
        one_wrist_above_shoulder = left_wrist_above_shoulder or right_wrist_above_shoulder
        elbows_at_shoulder_level = (left_elbow_at_shoulder or right_elbow_at_shoulder)
        
        # NEW: Detect upward movement by comparing current and previous wrist positions
        moving_upward = False
        
        # For left arm movement
        if left_wrist_y is not None and state['prev_left_wrist_y'] is not None:
            left_moving_up = left_wrist_y < state['prev_left_wrist_y']
            angles['LMovingUp'] = {
                'value': 1 if left_moving_up else 0,
                'position': {
                    'x': left_wrist['x'] - 0.1,
                    'y': left_wrist['y']
                }
            }
        else:
            left_moving_up = False
            
        # For right arm movement
        if right_wrist_y is not None and state['prev_right_wrist_y'] is not None:
            right_moving_up = right_wrist_y < state['prev_right_wrist_y']
            angles['RMovingUp'] = {
                'value': 1 if right_moving_up else 0,
                'position': {
                    'x': right_wrist['x'] + 0.1,
                    'y': right_wrist['y']
                }
            }
        else:
            right_moving_up = False
            
        # Consider moving upward if either arm is clearly moving up
        # Use a significant threshold to avoid minor fluctuations
        if (left_moving_up and left_wrist_y is not None and state['prev_left_wrist_y'] is not None and 
           (state['prev_left_wrist_y'] - left_wrist_y > 0.01)):
            moving_upward = True
        if (right_moving_up and right_wrist_y is not None and state['prev_right_wrist_y'] is not None and 
           (state['prev_right_wrist_y'] - right_wrist_y > 0.01)):
            moving_upward = True
        
        # Process shoulder press detection with position tracking
        if avg_elbow_angle is not None:
            # DOWN POSITION: Arms bent, elbows near shoulders
            in_down_position = (avg_elbow_angle < 120) and (elbows_at_shoulder_level or not both_wrists_above_shoulder)
            
            # UP POSITION: Arms extended, wrists above shoulders
            in_up_position = (avg_elbow_angle > 140 and both_wrists_above_shoulder) or (avg_elbow_angle > 150 and one_wrist_above_shoulder)
            
            # STATE TRANSITIONS with movement verification
            if in_down_position:
                # If we were previously in the up position and now in down, we're ready for next rep
                if state['stage'] == "up":
                    state['stage'] = "down"
                    feedback = "Ready for next rep"
                elif state['stage'] == "down":
                    feedback = "Ready position"
                
                state['holdStart'] = current_time
                
            elif in_up_position:
                # NEW: Only count rep if we were in down position AND we detected upward movement
                if state['stage'] == "down" and moving_upward:
                    if current_time - state['lastRepTime'] > rep_cooldown:
                        state['repCounter'] += 1
                        state['lastRepTime'] = current_time
                        state['stage'] = "up"
                        feedback = "Rep complete!"
                    else:
                        feedback = "Slow down slightly"
                elif state['stage'] == "up":
                    feedback = "Lower arms to shoulder level for next rep"
            
            # FORM FEEDBACK
            elif one_wrist_above_shoulder and not both_wrists_above_shoulder:
                feedback = "Press both arms evenly"
            elif not feedback:
                if state['stage'] == "up":
                    feedback = "Lower arms to shoulder level"
                else:
                    feedback = "Continue the movement"

        # Update position history for next frame
        state['prev_left_wrist_y'] = left_wrist_y
        state['prev_right_wrist_y'] = right_wrist_y

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
    """Process landmarks for floor tricep extension exercise with single-arm support"""
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
        
        # Check visibility of arms
        left_arm_visible = all(k in left_shoulder for k in ['x', 'y']) and all(k in left_elbow for k in ['x', 'y']) and all(k in left_wrist for k in ['x', 'y'])
        right_arm_visible = all(k in right_shoulder for k in ['x', 'y']) and all(k in right_elbow for k in ['x', 'y']) and all(k in right_wrist for k in ['x', 'y'])
        
        # If neither arm is visible, provide feedback
        if not (left_arm_visible or right_arm_visible):
            return {
                'repCounter': state['repCounter'],
                'stage': state['stage'],
                'feedback': "Cannot see arms clearly - adjust camera angle",
                'angles': angles
            }

        # Calculate and store left arm angle if visible
        if left_arm_visible:
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
            if left_angle > 130 and state['leftArmStage'] == "down":  # Arm is extended
                if current_time - state['leftArmHoldStart'] > hold_threshold:
                    left_extension_detected = True
                    state['leftArmStage'] = "up"

        # Calculate and store right arm angle if visible
        if right_arm_visible:
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
            if right_angle > 130 and state['rightArmStage'] == "down":  # Arm is extended
                if current_time - state['rightArmHoldStart'] > hold_threshold:
                    right_extension_detected = True
                    state['rightArmStage'] = "up"

        # MODIFIED: Count rep based on visible arms
        extension_detected = False
        if left_arm_visible and right_arm_visible:
            # Both arms visible - require both to extend
            extension_detected = left_extension_detected and right_extension_detected
            if extension_detected:
                feedback = "Good rep! Both arms extended."
            elif left_extension_detected and not right_extension_detected:
                feedback = "Extend your right arm too"
            elif not left_extension_detected and right_extension_detected:
                feedback = "Extend your left arm too"
        elif left_arm_visible:
            # Only left arm visible - only require left arm to extend
            extension_detected = left_extension_detected
            if extension_detected:
                feedback = "Left arm rep detected."
            else:
                feedback = "Extend your left arm fully"
        elif right_arm_visible:
            # Only right arm visible - only require right arm to extend
            extension_detected = right_extension_detected
            if extension_detected:
                feedback = "Right arm rep detected."
            else:
                feedback = "Extend your right arm fully"
                
        # Count the rep if extension detected and cooldown passed
        if extension_detected and current_time - state['lastRepTime'] > rep_cooldown:
            state['repCounter'] += 1
            state['lastRepTime'] = current_time

        return {
            'repCounter': state['repCounter'],
            'stage': 'up' if extension_detected else 'down',
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
    """Process landmarks for lunge exercise with stricter movement verification"""
    try:
        # Get landmarks for both sides of the body
        left_hip = landmarks[23]
        left_knee = landmarks[25]
        left_ankle = landmarks[27]
        right_hip = landmarks[24]
        right_knee = landmarks[26]
        right_ankle = landmarks[28]

        # Check if at least one leg is fully visible
        left_leg_visible = all(point and all(k in point for k in ['x', 'y']) 
                              for point in [left_hip, left_knee, left_ankle])
        right_leg_visible = all(point and all(k in point for k in ['x', 'y']) 
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
        if left_leg_visible and right_leg_visible:
            knee_height_diff = abs(left_knee['y'] - right_knee['y'])
            angles['KneeDiff'] = {
                'value': knee_height_diff * 100,
                'position': {
                    'x': (left_knee['x'] + right_knee['x']) / 2,
                    'y': (left_knee['y'] + right_knee['y']) / 2
                }
            }

        # IMPROVED POSITION TRACKING
        # Initialize tracking values if they don't exist
        if 'prev_left_knee_y' not in state:
            state['prev_left_knee_y'] = None
        if 'prev_right_knee_y' not in state:
            state['prev_right_knee_y'] = None
        if 'movement_history' not in state:
            state['movement_history'] = []
        if 'angle_history' not in state:
            state['angle_history'] = []
        
        # RECORD MOVEMENT DATA
        # Track knee positions and movements
        left_knee_movement = 0
        right_knee_movement = 0
        
        if left_leg_visible and state['prev_left_knee_y'] is not None:
            left_knee_movement = left_knee['y'] - state['prev_left_knee_y']
            angles['LKneeMove'] = {
                'value': left_knee_movement * 100,
                'position': {
                    'x': left_knee['x'] - 0.1,
                    'y': left_knee['y']
                }
            }
        
        if right_leg_visible and state['prev_right_knee_y'] is not None:
            right_knee_movement = right_knee['y'] - state['prev_right_knee_y']
            angles['RKneeMove'] = {
                'value': right_knee_movement * 100,
                'position': {
                    'x': right_knee['x'] + 0.1,
                    'y': right_knee['y']
                }
            }
        
        # Store movement data in history (keep last 5 frames)
        movement_data = {
            'left': left_knee_movement,
            'right': right_knee_movement,
            'time': current_time
        }
        state['movement_history'].append(movement_data)
        if len(state['movement_history']) > 5:
            state['movement_history'].pop(0)
            
        # Store angle data in history (keep last 5 frames)
        angle_data = {
            'left': left_leg_angle,
            'right': right_leg_angle,
            'time': current_time
        }
        state['angle_history'].append(angle_data)
        if len(state['angle_history']) > 5:
            state['angle_history'].pop(0)
            
        # VERIFY SUSTAINED MOVEMENT
        # Calculate average movement over the last few frames to detect real movement vs jitter
        left_avg_movement = 0
        right_avg_movement = 0
        movement_count = 0
        
        for data in state['movement_history']:
            if data['left'] is not None:
                left_avg_movement += data['left']
                movement_count += 1
            if data['right'] is not None:
                right_avg_movement += data['right']
                movement_count += 1
                
        if movement_count > 0:
            left_avg_movement /= movement_count
            right_avg_movement /= movement_count
            
        # VERIFY SIGNIFICANT ANGLE CHANGE
        # Calculate how much the leg angles have changed recently
        left_angle_change = 0
        right_angle_change = 0
        
        if len(state['angle_history']) >= 2:
            latest = state['angle_history'][-1]
            previous = state['angle_history'][0]
            
            if latest['left'] is not None and previous['left'] is not None:
                left_angle_change = abs(latest['left'] - previous['left'])
                
            if latest['right'] is not None and previous['right'] is not None:
                right_angle_change = abs(latest['right'] - previous['right'])
        
        # DETERMINE IF ACTUAL EXERCISE MOVEMENT IS HAPPENING
        # We consider it significant movement if:
        # 1. There's consistent movement trend in knee position over multiple frames
        # 2. There's significant change in knee angles
        significant_movement = False
        significant_angle_change = (left_angle_change > 20 or right_angle_change > 20)
        consistent_movement = (abs(left_avg_movement) > 0.01 or abs(right_avg_movement) > 0.01)
        
        if significant_angle_change and consistent_movement:
            significant_movement = True
            angles['SignificantMove'] = {
                'value': 1,
                'position': {
                    'x': 0.1,
                    'y': 0.1
                }
            }
        
        # Store current positions for next frame comparison
        if left_leg_visible:
            state['prev_left_knee_y'] = left_knee['y']
        if right_leg_visible:
            state['prev_right_knee_y'] = right_knee['y']

        # POSITION DETECTION
        # Standing position - both legs relatively straight
        standing_detected = False
        if left_leg_visible and right_leg_visible:
            # Both legs visible - check if both are straight-ish
            standing_detected = (left_leg_angle > 150 and right_leg_angle > 150 and knee_height_diff < 0.15)
        elif left_leg_visible and left_leg_angle > 150:
            # Only left leg visible and it's straight
            standing_detected = True
        elif right_leg_visible and right_leg_angle > 150:
            # Only right leg visible and it's straight
            standing_detected = True
            
        # Lunge position - one leg bent
        lunge_detected = False
        
        # Check for lunge position with more lenient criteria
        if left_leg_visible and right_leg_visible:
            # One leg is sufficiently bent AND knees have height difference
            lunge_detected = ((left_leg_angle < 110 or right_leg_angle < 110) and knee_height_diff > 0.2)
        elif left_leg_visible and left_leg_angle < 110:
            # Only left leg visible and it's bent
            lunge_detected = True
        elif right_leg_visible and right_leg_angle < 110:
            # Only right leg visible and it's bent
            lunge_detected = True

        # STATE TRANSITIONS WITH STRICTER VERIFICATION
        feedback = ""
        
        # Handle standing position detection (up position)
        if standing_detected:
            if state['stage'] == "down":
                # Only transition if we see significant movement
                if significant_movement:
                    state['stage'] = "up"
                    feedback = "Ready for next lunge"
                else:
                    # Not enough movement to confirm transition
                    feedback = "Return to standing position"
            elif state['stage'] == "up":
                feedback = "Standing position"

        # Handle lunge position detection (down position)
        if lunge_detected:
            # STRICTER REP COUNTING: Only count when:
            # 1. We're in standing position
            # 2. There's significant movement AND angle change
            # 3. Cooldown has passed
            if state['stage'] == "up" and significant_movement:
                if current_time - state['lastRepTime'] > rep_cooldown:
                    state['stage'] = "down"
                    state['repCounter'] += 1
                    state['lastRepTime'] = current_time
                    feedback = "Rep counted! Good lunge."
                else:
                    feedback = "Slow down slightly"
            elif state['stage'] == "down":
                feedback = "Return to standing position"

        # Default feedback if none set yet
        if not feedback:
            if state['stage'] == "up":
                feedback = "Step forward into lunge position"
            else:
                feedback = "Return to standing position"

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
