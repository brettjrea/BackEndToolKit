from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import threading
import select
import re
import queue

app = Flask(__name__)
CORS(app, resources={r"*": {"origins": "*"}})

chat_process = None
binary_init_thread = None

def execute_binary(input_data):
    global chat_process

    def read_output(output_queue):
        while True:
            output_data = chat_process.stdout.readline().strip()
            output_queue.put(output_data)

    try:
        print(f"Sending input: {input_data}")  # Debugging print
        chat_process.stdin.write(input_data + "\n")
        chat_process.stdin.flush()

        output_queue = queue.Queue()
        output_thread = threading.Thread(target=read_output, args=(output_queue,))
        output_thread.daemon = True
        output_thread.start()

        # Wait for the process to output something
        while True:
            try:
                output_data = output_queue.get(timeout=0.1)
                # Strip out escape codes from the output
                output_data = re.sub(r'\x1b\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]', '', output_data)
                # Strip out leading '>' character from the output
                output_data = output_data.lstrip('>')
                print(f"Output: {output_data}")  # Debugging print
                return output_data
            except queue.Empty:
                pass
    except BrokenPipeError:
        print("Chat process is not yet ready to receive input.")
        return ""
    except Exception as e:
        print(f"Exception: {e}")  # Debugging print
        return ""


def initialize_binary(args, chat_binary=None):
    global chat_process

    if chat_binary is None:
        cmd = ["./chat"]  # Default chat binary
    else:
        cmd = [chat_binary]

    cmd += args

    try:
        print(f"Executing command: {cmd}")  # Debugging print
        chat_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    except Exception as e:
        print(f"Exception: {e}")  # Debugging print


@app.route('/configure', methods=['POST'])
def configure():
    data = request.json
    args = data.get('args', [])
    chat_binary = data.get('chat_binary', './chat')

    global binary_init_thread
    if binary_init_thread and binary_init_thread.is_alive():
        return jsonify({"status": "error", "message": "Chat binary is already running."})

    binary_init_thread = threading.Thread(target=initialize_binary, args=(args, chat_binary))
    binary_init_thread.start()
    binary_init_thread.join()

    initial_output = execute_binary("")  # Get the initial output

    return jsonify({"status": "success", "message": "Chat binary started with the provided arguments.", "response": [initial_output]})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    input_data = data.get('input', '')  # Use the get method with a default value of an empty string
    output_data = execute_binary(input_data)
    response = {'output': output_data}
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
