import threading
import queue
import sys
import time
from datetime import datetime
import logging
import select
import os
import termios
import tty


class SimpleTerminalInterface:
    def __init__(self):
        self.status = "Initializing..."
        self.next_run_time = None
        self.command_queue = queue.Queue()
        self.running = True
        self.force_run_requested = False
        self._setup_input_thread()
        
    def _setup_input_thread(self):
    self.input_thread = threading.Thread(target=self._input_listener)
    self.input_thread.daemon = True
    self.input_thread.start()

    def _is_data_available(self):
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    def _getch(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
        
    def _input_listener(self):
        while self.running:
            if self._is_data_available():
                key = self._getch()
                if key == 'f':
                    print("\nForce a run now? (y/n): ", end='', flush=True)
                    confirm = self._getch()
                    print(confirm)
                    if confirm.lower() == 'y':
                        self.force_run_requested = True
                        self.command_queue.put("force_run")
                        print("Run forced!")
                    else:
                        print("Run cancelled.")
                elif key == 'q':
                    print("\nQuit? (y/n): ", end='', flush=True)
                    confirm = self._getch()
                    print(confirm)
                    if confirm.lower() == 'y':
                        self.running = False
                        self.command_queue.put("quit")
                        print("Shutting down...")
                    else:
                        print("Quit cancelled.")
                # Clear the input buffer
                while self._is_data_available():
                    self._getch()
            time.sleep(0.1)

    def display_status(self):
        print("\n" + "=" * 60)
        print(f"FACEBOOK MARKETPLACE SCRAPER")
        print("=" * 60)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nCurrent Time: {current_time}")
        
        print(f"\nStatus: {self.status}")
        
        if self.next_run_time:
            time_remaining = self.next_run_time - datetime.now()
            if time_remaining.total_seconds() > 0:
                minutes, seconds = divmod(int(time_remaining.total_seconds()), 60)
                print(f"Next Run: {self.next_run_time.strftime('%H:%M:%S')} (in {minutes}m {seconds}s)")
            else:
                print("Next Run: Imminent")
        
        print("\nCommands:")
        print("  f - Force a run now")
        print("  q - Quit application")
        print("\n" + "-" * 60)

    def update_status(self, status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status = f"{timestamp} | {status}"
        print(f"\n{self.status}")
        logging.info(status)

    def set_next_run_time(self, next_time):
        self.next_run_time = next_time
        print(f"\nNext run scheduled for: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def check_for_force_run(self):
        if self.force_run_requested:
            self.force_run_requested = False
            return True
        return False

    def get_command(self):
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None

    def start(self):
        self.display_status()

    def stop(self):
        self.running = False
        if hasattr(self, 'input_thread'):
            self.input_thread.join(timeout=1.0)