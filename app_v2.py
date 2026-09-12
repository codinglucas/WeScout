from flask import Flask, request, jsonify
from flask_cors import CORS
from sofascore import execute
from start import get_player_list

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Position mapping: name -> ID
POSITION_MAP = {
    'gk': 1,
    'sweeper': 2,
    'cb': 3,
    'lb': 4,
    'rb': 5,
    'cdm': 6,
    'cm': 7,
    'rm': 8,
    'lm': 9,
    'cam': 10,
    'lw': 11,
    'rw': 12,
    'st': 13,
    'cf': 14
}

@app.route('/api/players/search', methods=['GET'])
def search_players():
    """
    Search players with filters
    Query params: min_age, max_age, min_value, max_value, position
    """
    try:
        # Get query parameters
        min_age = request.args.get('min_age', type=int, default=16)
        max_age = request.args.get('max_age', type=int, default=40)
        min_value = request.args.get('min_value', type=int, default=0)
        max_value = request.args.get('max_value', type=int, default=100000000)
        position = request.args.get('position', type=str, default='').lower()
        
        # Convert position name to ID
        position_id = POSITION_MAP.get(position, None)
        
        # Validate inputs
        if min_age and max_age and min_age > max_age:
            return jsonify({'success': False, 'error': 'min_age cannot be greater than max_age'}), 400
        
        if min_value and max_value and min_value > max_value:
            return jsonify({'success': False, 'error': 'min_value cannot be greater than max_value'}), 400
        
        print(f"Searching with: min_age={min_age}, max_age={max_age}, max_value={max_value}, position_id={position_id}")
        
        # Get player data from your existing functions
        players = execute()



    except Exception as e:
            print(f"Error in search_players: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    return 


if __name__ == "__main__":
    app.run(debug=True)
    