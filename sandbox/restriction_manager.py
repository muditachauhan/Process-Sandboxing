# sandbox/restriction_manager.py
import socket

class RestrictionManager:
    """
    Simulates network blocking by monkey-patching socket.socket.
    (This does not block child process network calls if they spawn separate processes
    that import socket after we patch. For a demo it simulates blocking in the same interpreter.)
    """
    def __init__(self):
        self.network_blocked = True
        self._original_socket = socket.socket

    def toggle_network(self):
        self.network_blocked = not self.network_blocked
        return self.network_blocked

    def simulate_network_block(self):
        if self.network_blocked:
            socket.socket = self._blocked_socket
        else:
            socket.socket = self._original_socket

    def _blocked_socket(self, *a, **kw):
        raise ConnectionError("Network access blocked in sandbox (simulated).")

    def is_network_allowed(self):
        return not self.network_blocked

    def restore(self):
        socket.socket = self._original_socket
