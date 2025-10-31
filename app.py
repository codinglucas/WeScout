from flask import Flask, request, jsonify
from flask_cors import CORS
from sofascore import get_player_data, dataframe_organizer
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
        player_list, club_list, price_list, int_price_list = get_player_list(
            min_age, 
            max_age, 
            max_value,  # This is max_price in your function
            position_id
        )
        
        print(f"Found {len(player_list)} players from get_player_list")
        
        # Get comprehensive player stats from sofascore
        (id_list, rating_list, goal_list, assists_list, key_passes_list, 
         minutes_played_list, tackles_list, interceptions_list, dribbled_past_list,
         big_chances_created_list, accurate_passes_list, total_passes_list) = get_player_data(player_list)
        
        # Organize data into DataFrame with all stats
        df = dataframe_organizer(
            id_list, rating_list, price_list, goal_list, player_list, club_list, 
            assists_list, key_passes_list, int_price_list, minutes_played_list,
            tackles_list, interceptions_list, dribbled_past_list, 
            big_chances_created_list, accurate_passes_list, total_passes_list
        )
        
        print(f"DataFrame created with {len(df)} rows")
        print("DataFrame columns:", df.columns.tolist())
        
        # Filter by min_value if provided (using "Actual Price" column from your DataFrame)
        if min_value and min_value > 0:
            df = df[df['Actual Price'] >= min_value]
            print(f"After min_value filter: {len(df)} players")
        
        # Convert DataFrame to JSON-friendly format
        # Rename columns to match frontend expectations
        df_renamed = df.rename(columns={
            'Player': 'player_name',
            'Club': 'club_name',
            'Price': 'price',
            'Actual Price': 'price_int',
            'Rating': 'rating',
            'Goals': 'goals',
            'Assists': 'assists',
            'Key Passes': 'key_passes',
            'ID': 'player_id',
            'BCR': 'bcr',
            'Minutes Played': 'minutes_played',
            'Tackles': 'tackles',
            'Interceptions': 'interceptions',
            'Dribbled Past': 'dribbled_past',
            'Big Chances Created': 'big_chances_created',
            'Accurate Passes': 'accurate_passes',
            'Total Passes': 'total_passes',
            'Tackles Per 90': 'tackles_per_90',
            'Interceptions Per 90': 'interceptions_per_90',
            'Dribbled Past Per 90': 'dribbled_past_per_90',
            'Pass Completion %': 'pass_completion'
        })
        
        # Add position info if available
        if position:
            df_renamed['position'] = position.upper()
        
        # IMPORTANT: Replace NaN and inf values with None for valid JSON
        df_renamed = df_renamed.replace({float('nan'): None, float('inf'): None, float('-inf'): None})
        
        # Convert "N/A" strings to None
        df_renamed = df_renamed.replace('N/A', None)
        
        # Convert to list of dictionaries
        players_data = df_renamed.to_dict('records')
        
        print(f"Returning {len(players_data)} players")
        
        return jsonify({
            'success': True,
            'count': len(players_data),
            'players': players_data
        }), 200
        
    except Exception as e:
        print(f"Error in search_players: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get all available positions"""
    positions = [
        {'id': 1, 'code': 'gk', 'name': 'Goalkeeper'},
        {'id': 2, 'code': 'sweeper', 'name': 'Sweeper'},
        {'id': 3, 'code': 'cb', 'name': 'Center Back'},
        {'id': 4, 'code': 'lb', 'name': 'Left Back'},
        {'id': 5, 'code': 'rb', 'name': 'Right Back'},
        {'id': 6, 'code': 'cdm', 'name': 'Defensive Midfielder'},
        {'id': 7, 'code': 'cm', 'name': 'Central Midfielder'},
        {'id': 8, 'code': 'rm', 'name': 'Right Midfielder'},
        {'id': 9, 'code': 'lm', 'name': 'Left Midfielder'},
        {'id': 10, 'code': 'cam', 'name': 'Attacking Midfielder'},
        {'id': 11, 'code': 'lw', 'name': 'Left Wing'},
        {'id': 12, 'code': 'rw', 'name': 'Right Wing'},
        {'id': 13, 'code': 'st', 'name': 'Striker'},
        {'id': 14, 'code': 'cf', 'name': 'Center Forward'}
    ]
    
    return jsonify({
        'success': True,
        'positions': positions
    }), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'message': 'API is running'
    }), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)