#!/usr/bin/env python
"""Test if the FastAPI app imports and works"""
import sys
sys.path.insert(0, 'src')

try:
    print("Importing FastAPI app...")
    from main import app
    print("✅ FastAPI app imported successfully!")
    
    print("\n📋 Available endpoints:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.path}")
    
    print("\n🎯 Testing /generate/architecture endpoint...")
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    response = client.post(
        "/generate/architecture",
        json={
            "user_input": "Build a simple user authentication system",
            "requirement_doc": "Should support login with email and password"
        }
    )
    
    print(f"\nResponse Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ API endpoint works!")
        data = response.json()
        print(f"  - Agent Type: {data.get('agent_type')}")
        print(f"  - Document ID: {data.get('id')}")
        print(f"  - Output length: {len(data.get('output', ''))} chars")
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"  Message: {response.text}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
