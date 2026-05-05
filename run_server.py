#!/usr/bin/env python3
"""
Simple script to run the document upload server.
"""
import uvicorn

if __name__ == "__main__":
    print("Starting Document Upload Service...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    print("Health check at: http://localhost:8000/health")
    print("\nPress Ctrl+C to stop the server")
    
    uvicorn.run(
        "app.main:app",  # Import string format
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )