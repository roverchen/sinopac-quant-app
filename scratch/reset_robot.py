import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import save_robot_status
from datetime import datetime

status_dict = {
    "status": "Idle",
    "message": "Manual reset from stuck scanning state.",
    "timestamp": datetime.now().isoformat(),
    "last_updated": datetime.now().isoformat(),
    "heartbeat": datetime.now().isoformat()
}

save_robot_status(status_dict)
print("Robot status has been reset to Idle.")
