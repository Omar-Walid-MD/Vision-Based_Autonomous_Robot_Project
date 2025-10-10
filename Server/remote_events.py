class RemoteClientHandler:
    def __init__(self,sio):
        
        self.connected = False
        
        # SERVER EVENTS
        @sio.event
        async def connect_remote_client(sid):
            self.connected = True
            
        @sio.event
        async def remote_request_status(sid):
            sio.emit("remote_receive_status","status")
