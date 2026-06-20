import socketio
from server_state import robot_position, robot_components, connected_clients, map_data, nodes, robot_tasks


class RemoteClientHandler:
    def __init__(self, sio):
        self.sio = sio
        self.register_events()

    async def client_connected(self, sid):
        connected_clients.add(sid)

        print(f"[REMOTE] Client connected: {sid}")

        await self.sio.enter_room(sid, "clients")

        await self.sio.emit(
            "map_data",
            map_data,
            to=sid
        )

        await self.sio.emit(
            "status_list",
            {
                "components": robot_components,
                "tasks": robot_tasks,
                "robot_position": robot_position
            },
            to=sid
        )

    async def client_disconnected(self, sid):
        connected_clients.discard(sid)
        print(f"[REMOTE] Client disconnected: {sid}")

    def register_events(self):

        @self.sio.event
        async def send_task(sid, task):
            print(f"task received from client ({sid}): {task}")


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