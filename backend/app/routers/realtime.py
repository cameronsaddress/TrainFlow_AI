from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict

realtime_router = APIRouter(tags=["realtime"])

# Connection Manager
class ConnectionManager:
    def __init__(self):
        # Map flow_id -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, flow_id: str):
        await websocket.accept()
        if flow_id not in self.active_connections:
            self.active_connections[flow_id] = []
        self.active_connections[flow_id].append(websocket)

    def disconnect(self, websocket: WebSocket, flow_id: str):
        if flow_id in self.active_connections:
            if websocket in self.active_connections[flow_id]:
                self.active_connections[flow_id].remove(websocket)
            if not self.active_connections[flow_id]:
                del self.active_connections[flow_id]

    async def broadcast(self, message: dict, flow_id: str, sender: WebSocket):
        if flow_id in self.active_connections:
            for connection in self.active_connections[flow_id]:
                if connection != sender: # Don't echo back to sender if managing local state optimistically
                    await connection.send_json(message)

manager = ConnectionManager()

@realtime_router.websocket("/ws/{flow_id}")
async def websocket_endpoint(websocket: WebSocket, flow_id: str):
    """
    Gap 2: Real-Time Collaborative Editing via WebSockets.
    """
    await manager.connect(websocket, flow_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast change to others in the room
            # Data format: {"type": "node_drag", "node_id": "1", "pos": {...}}
            await manager.broadcast(data, flow_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, flow_id)
