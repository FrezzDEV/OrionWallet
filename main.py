from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/user_data_api')
def user_data_api():
    user_id = int(request.args.get('user_id'))
    conn = sqlite3.connect('orion_wallet.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = c.fetchone()
    conn.close()
    if user_data:
        return jsonify({
            'status': 'success',
            'user_id': user_id,
            'username': user_data[1],
            'balance': user_data[2],
            'stars': user_data[3]
        })
    return jsonify({'status': 'error', 'message': 'User not found'})

@app.route('/crypto_rates_api')
def crypto_rates_api():
    return jsonify(get_crypto_rates())

if __name__ == '__main__':
    app.run()
