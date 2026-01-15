import time
import json
import socket
import threading
import subprocess
from pathlib import Path

from ..logs.logger import get_logger

# MPVControl v2

class MPVControl:
    def __init__(self, sock_path = Path.home() / "Project-Ibuki" / "mpv.sock"):
        self.logger = get_logger("MPVControl")
        self.sock_path = sock_path
        self.process = None
        self.socket = None
        self.running = False
        self._progress_thread = None
        self.on_exit = None
        self._recv_buffer = ""
        self.current_duration = None
        self._current_position = None

    def _cleanup_socket(self):
        try:
            Path(self.sock_path).unlink()
        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.error(f"Failed to clean up socket: {e} :(")

    def launch(self, url, start_time=0, extra_args=None):
        if extra_args is None:
            extra_args = []

        self._cleanup_socket()

        Path(self.sock_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
                  "mpv",
                  url,
                  f"--start={start_time}",
                  f"--input-ipc-server={self.sock_path}",
                  "--force-window=immediate",
                  "--no-terminal",
                  "--idle=no",
                  "--keep-open=no",
                  "--msg-level=ipc=v",
              ] + extra_args

        self.logger.info(f"Launching MPV with socket: {self.sock_path}")
        self.logger.debug(f"MPV command: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            self.logger.error(f"Failed to start MPV process: {e}")
            return False

        self.running = True
        self.current_duration = None
        self._current_position = None
        self._recv_buffer = ""

        time.sleep(1.0)  # Increased from 0.5

        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate()
            self.logger.error(f"MPV died immediately! Exit code: {self.process.returncode} :(")
            self.logger.error(f"STDOUT: {stdout}")
            self.logger.error(f"STDERR: {stderr}")
            self.running = False
            return False

        connected = self._connect_to_socket(max_attempts=30, delay=0.2)

        if not connected:
            self.logger.error("Failed to connect to MPV socket!")
            self.running = False
            return False

        threading.Thread(target=self._listen_ipc, daemon=True).start()
        return True

    def _listen_ipc(self):
        """Listen for JSON events from MPV with proper buffer handling."""
        if not self.socket:
            self.logger.error("Cannot start IPC listener - socket is None!")
            return

        try:
            while self.running:
                if not self._process_socket_data():
                    break
        except Exception as e:
            self.logger.error(f"Error in MPV IPC listener: {e} :/")
        finally:
            self.running = False
            self.close()

    def _process_socket_data(self):
        """Read and process data from a socket. Returns False if it should stop."""
        try:
            data = self.socket.recv(4096)
            if not data:
                return False

            self._recv_buffer += data.decode("utf-8")
            self._process_buffered_lines()
            return True

        except socket.timeout:
            return True

    def _process_buffered_lines(self):
        """Process all complete lines in the buffer"""
        while "\n" in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split("\n", 1)
            if line.strip():
                self._handle_ipc_line(line)

    def _handle_ipc_line(self, line):
        """Parse and handle a single IPC message line"""
        try:
            msg = json.loads(line)

        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON decode error {e} :/")
            return

        self._handle_ipc_message(msg)

    def _handle_ipc_message(self, msg):
        """Process a parsed IPC message"""
        # Handle successful responses with data
        if msg.get("error") == "success" and "data" in msg:
            self._handle_response_data(msg)

        if msg.get("event") == "end-file":
            self._handle_end_file()

    def _handle_response_data(self, msg):
        """Handle response data based on request_id"""
        request_id = msg.get("request_id", 0)
        if request_id == 1:
            self._current_position = msg["data"]

        elif request_id == 2:
            self.current_duration = msg["data"]

    def _handle_end_file(self):
        """Handle end-file event"""
        self.running = False
        if self.on_exit:
            self.on_exit()

    def _connect_to_socket(self, max_attempts=30, delay=0.2):
        """Separate connection logic with better error handling"""
        for attempt in range(max_attempts):
            if not self._should_continue_connecting():
                return False

            if not self._socket_file_ready(delay):
                continue

            if self._attempt_connection(attempt):
                return True

            self._cleanup_failed_socket()
            time.sleep(delay)

        return False

    def _should_continue_connecting(self):
        """Check if an MPV process is still alive"""
        if self.process.poll() is not None:
            self.logger.error("MPV process died while waiting for socket")
            return False
        return True

    def _socket_file_ready(self, delay):
        """Check if a socket file exists"""
        if not Path(self.sock_path).exists():
            time.sleep(delay)
            return False
        return True

    def _attempt_connection(self, attempt):
        """Try to connect to the socket"""
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(2.0)
            self.socket.connect(str(self.sock_path))
            self.socket.settimeout(0.5)
            self.logger.info(f"Connected to MPV socket on attempt {attempt + 1}")
            return True
        except (ConnectionRefusedError, FileNotFoundError) as e:
            self.logger.debug(f"Attempt {attempt + 1}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected socket error on attempt {attempt + 1}: {e}")
            return False

    def _cleanup_failed_socket(self):
        """Close and cleanup socket on failure"""
        if hasattr(self, 'socket') and self.socket:
            try:
                self.socket.close()

            except Exception as e:
                self.logger.error(f"Failed to close socket: {e} :/")
            self.socket = None

    def send(self, command, args=None, request_id=0):
        """Send a command to MPV IPC with optional request_id for tracking responses."""
        if args is None:
            args = []

        try:
            payload = json.dumps({"command": [command] + args, "request_id": request_id})
            self.socket.send(payload.encode("utf-8") + b"\n")

        except Exception as e:
            self.logger.error(f"Failed to send command to MPV: {e} :/")

    def get_current_state(self):
        """Get current playback position and duration."""
        try:
            self.send("get_property", ["time-pos"], request_id=1)
            self.send("get_property", ["duration"], request_id=2)

            time.sleep(0.1)
            return self._current_position, self.current_duration

        except Exception as e:
            self.logger.error(f"Failed to get playback state: {e} :/")
            return None, None

    def start_progress_tracker(self, callback, interval=10):
        """Tracks MPV's actual playback time and duration."""

        def _track():
            while self.running:
                try:
                    position, duration = self.get_current_state()

                    if position is not None and duration is not None:
                        callback(int(position), int(duration))

                    elif position is not None:
                        self.logger.debug("Duration not available yet, using estimated")
                        callback(int(position), int(position) + 300)

                except Exception as e:
                    self.logger.error(f"Error tracking progress: {e} :/")

                time.sleep(interval)

        self._progress_thread = threading.Thread(target=_track, daemon=True)
        self._progress_thread.start()

    def get_elapsed_time(self):
        """Get current elapsed time synchronously."""
        position, _ = self.get_current_state()
        return int(position) if position is not None else 0

    def close(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception as e:
                self.logger.error(f"Failed to terminate MPV process: {e} :/")

        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.logger.error(f"Failed to terminate MPV socket: {e} :/")
                pass
        self._cleanup_socket()