import argparse
import time
import logging
import socket
from urllib.parse import urlparse
from flask import Flask, jsonify, request

import requests

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

def fetch_latest_block_number(rpc_url):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    response = requests.post(rpc_url, json=payload)
    if response.status_code == 200:
        result = response.json().get('result', None)
        if result is not None:
            return int(result, 16)
    return None


def get_hostname(url):
    parsed_url = urlparse(url)
    return parsed_url.hostname


def is_port_open(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        host = get_hostname(host)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logging.error(f"Error checking port {port}: {str(e)}")
        return False


def fetch_block_details(rpc_url, block_number):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False],
        "id": 1
    }
    response = requests.post(rpc_url, json=payload)
    if response.status_code == 200:
        return response.json().get('result', {})
    return {}

def check_block_progression(rpc_url, timeout):
    start_time = time.time()
    initial_block_number = fetch_latest_block_number(rpc_url)
    if initial_block_number is None:
        return False

    while time.time() - start_time < timeout:
        current_block_number = fetch_latest_block_number(rpc_url)
        if current_block_number is not None and current_block_number > initial_block_number:
            return True
        time.sleep(5)  # Check every 5 seconds

    return False

def main(rpc_url, reference_url='https://rpc.rollux.com', timeout=30):
    logging.info("Starting the script")
    # Port scan
    ports_to_check = [30303, 9003, 30304]
    port_status = {port: is_port_open(rpc_url, port) for port in ports_to_check}

    all_ports_open = all(port_status.values())

    for port, status in port_status.items():
        if status:
            logging.info(f"Port {port} is open.")
        else:
            logging.error(f"Port {port} is closed.")

    latest_block_number = fetch_latest_block_number(reference_url)
    if latest_block_number is None:
        logging.error("Failed to fetch the latest block number from https://rpc.rollux.com")
        return

    reference_block_details = fetch_block_details(reference_url, latest_block_number)
    target_block_details = fetch_block_details(rpc_url, latest_block_number)
    reference_block_hash = reference_block_details.get('hash')
    target_block_hash = target_block_details.get('hash')
    hash_check_pass = (reference_block_hash == target_block_hash)
    block_progression_pass = check_block_progression(rpc_url, timeout)
    port_check_pass = all_ports_open  # Additional condition

    if hash_check_pass:
        logging.info("Hash check passed.")
    else:
        logging.error(f"Hash check failed, For block {latest_block_number}, "
                      f"given rpc returns {target_block_hash}, correct hash was {reference_block_hash}")

    if block_progression_pass:
        logging.info("Block progression check passed.")
    else:
        logging.error("Block progression check failed.")

    if port_check_pass:
        logging.info("All specified ports are open. Port check passed.")
    else:
        logging.error("One or more specified ports are closed. Port check failed.")

    logging.info(
        f"Script completed. Hash Check: {'Pass' if hash_check_pass else 'Fail'}, Block Progression Check: {'Pass' if block_progression_pass else 'Fail'}, Port Check: {'Pass' if port_check_pass else 'Fail'}")


def perform_checks(rpc_url, reference_url='https://rpc.rollux.com', timeout=30):
    port_results = {port: is_port_open(rpc_url, port) for port in [30303, 9003, 30304, 8369, 18369]}
    latest_block_number = fetch_latest_block_number(reference_url)
    reference_block_details = fetch_block_details(reference_url, latest_block_number)
    target_block_details = fetch_block_details(rpc_url, latest_block_number)
    results = {
        'port_status': port_results,
        'block_hash_check': reference_block_details.get('hash') == target_block_details.get('hash'),
        'block_progression': check_block_progression(rpc_url, timeout)
    }
    return results


@app.route('/api/check', methods=['GET'])
def api_check():
    rpc_url = request.args.get('rpc_url', type=str)
    if rpc_url:
        results = perform_checks(rpc_url)
        return jsonify(results)
    else:
        return jsonify({"error": "RPC URL is required"}), 400


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Check Rollux node synchronization and progression.")
    parser.add_argument('rpc_url', type=str, help='The RPC URL of the Rollux node to test.')
    parser.add_argument('--api-mode', action='store_true', help='Run in API mode')
    args = parser.parse_args()

    if args.api_mode:
        app.run(host='0.0.0.0', port=5000)
    else:
        main(args.rpc_url)
