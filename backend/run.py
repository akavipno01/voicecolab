import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("VOICE_CLONE_PORT", "3920")),
        reload=False,
    )
