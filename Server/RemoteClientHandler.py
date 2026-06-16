import socketio
from server_state import robot_position, robot_components, connected_clients, map_data, nodes, robot_tasks


class RemoteClientHandler:
    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self.register_events()

    # --------------------------
    # Event registration
    # --------------------------
    def register_events(self):

        @self.sio.event
        async def connect(sid):
            connected_clients.add(sid)
            print(f"[REMOTE] Client connected: {sid}")

            # --------------------------
            # SEND BOOTSTRAP DATA ONCE
            # --------------------------
            await self.sio.enter_room(sid, "clients")
            await self.sio.emit(
                "map_data",
                map_data,
                to=sid
            )

            # Optional: also send initial robot state
            await self.sio.emit(
                "status_list",
                {
                    "components": robot_components,
                    "tasks": robot_tasks,
                    "robot_position": robot_position
                },
                to=sid
            )

        @self.sio.event
        async def disconnect(sid):
            connected_clients.discard(sid)
            print(f"[REMOTE] Client disconnected: {sid}")
            
        @self.sio.event
        async def send_task(sid,task):
            print(f"task received from client ({sid}):{task}")


    # --------------------------
    # Broadcast helpers
    # --------------------------
    async def broadcast_status(self):
        """
        Send status to all connected remote clients
        """
        if not connected_clients:
            return

        print("broadcasting to clients")
        await self.sio.emit(
            "status_list",
            {
                "components": robot_components,
                "tasks": robot_tasks,
                "robot_position": robot_position
            },
            room="clients"
        )